using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Networking;
using System;
using System.IO;
using System.Text;
using UnityEngine.EventSystems;
using ProyectoAgentesVirtuales.UnityBridge;

[RequireComponent(typeof(Button))]
public class AgentMicRecorder : MonoBehaviour
{
    [Header("Backend")]
    public string transcribeUrl = "http://127.0.0.1:8000/transcribe";
    public string userId = "unity_user";
    public string sessionId = "default";
    public string ttsMode = "auto";
    public string workflow = "schedule";

    [Header("UI")]
    public Button recordButton;
    public Text statusText;
    public Dropdown microphoneDropdown;
    [SerializeField] private bool debugLogPayloads = false;
    [SerializeField] private Graphic micBackgroundGraphic;
    [SerializeField] private Graphic[] syncedToggleGraphics;
    [SerializeField] private string micRingObjectName = "MicRing";

    [Header("References")]
    public AgentBackendReceiver receiver;

    [Header("Microphone")]
    [Tooltip("Dejar vacío para usar el micrófono por defecto del sistema.")]
    public string microphoneDeviceName = string.Empty;

    [Header("Silence Trim")]
    [Tooltip("Si está activo, recorta silencio al inicio y al final antes de guardar/enviar.")]
    public bool trimSilence = true;
    [Tooltip("Umbral absoluto por muestra para considerar que hay voz o ruido útil.")]
    [Range(0.0001f, 0.2f)]
    public float silenceThreshold = 0.015f;
    [Tooltip("Margen en milisegundos que se conserva antes y después del audio detectado.")]
    [Range(0f, 1000f)]
    public float silencePaddingMs = 250f;

    private bool isRecording = false;
    private bool isStartingRecording = false;
    private AudioClip recordingClip;
    private string activeMicrophoneDevice = string.Empty;
    private int sampleRate = 16000;
    private int maxSeconds = 120;
    private float recordingStartedAt = -1f;
    private ColorBlock cachedButtonColors;
    private bool hasCachedButtonColors = false;
    private Image micRingImage;

    public bool IsRecording => isRecording;
    public bool IsStartingRecording => isStartingRecording;
    public int MaxRecordingSeconds => maxSeconds;
    public float CurrentRecordingSeconds
    {
        get
        {
            if ((!isRecording && !isStartingRecording) || recordingStartedAt < 0f)
            {
                return 0f;
            }

            return Mathf.Clamp(Time.unscaledTime - recordingStartedAt, 0f, maxSeconds);
        }
    }

    public float RemainingRecordingRatio
    {
        get
        {
            if (maxSeconds <= 0)
            {
                return 0f;
            }

            return 1f - Mathf.Clamp01(CurrentRecordingSeconds / maxSeconds);
        }
    }

    public float RecordingProgressRatio
    {
        get
        {
            if (maxSeconds <= 0)
            {
                return 0f;
            }

            return Mathf.Clamp01(CurrentRecordingSeconds / maxSeconds);
        }
    }

    private void Start()
    {
        RefreshMicrophones();

        if (recordButton == null)
        {
            recordButton = GetComponent<Button>();
        }

        if (recordButton != null)
        {
            cachedButtonColors = recordButton.colors;
            hasCachedButtonColors = true;
            recordButton.transition = Selectable.Transition.None;
            recordButton.onClick.AddListener(ToggleRecording);
        }

        ResolveToggleGraphics();
        ResolveMicRing();

        UpdateStatus();
    }

    private void OnDestroy()
    {
        if (recordButton != null)
        {
            recordButton.onClick.RemoveListener(ToggleRecording);
        }
    }

    private void Update()
    {
        UpdateMicRingVisual();
    }

    public void ToggleRecording()
    {
        if (isStartingRecording)
        {
            return;
        }

        if (!isRecording)
        {
            StartRecording();
        }
        else
        {
            StopRecordingAndSend();
        }
    }

    private void StartRecording()
    {
        if (Microphone.devices.Length == 0)
        {
            Debug.LogError("No hay dispositivos de microfono disponibles.");
            return;
        }

        string selectedDevice = ResolveMicrophoneDevice();
        if (string.IsNullOrWhiteSpace(selectedDevice))
        {
            Debug.LogError("No se pudo resolver un microfono valido.");
            return;
        }

        activeMicrophoneDevice = selectedDevice;
        isStartingRecording = true;
        recordingStartedAt = Time.unscaledTime;
        recordingClip = Microphone.Start(selectedDevice, false, maxSeconds, sampleRate);
        StartCoroutine(WaitForMicrophoneStart(selectedDevice));
    }

    private IEnumerator WaitForMicrophoneStart(string selectedDevice)
    {
        const float timeoutSeconds = 2.0f;
        float elapsed = 0f;

        while (elapsed < timeoutSeconds && Microphone.GetPosition(selectedDevice) <= 0)
        {
            elapsed += Time.unscaledDeltaTime;
            yield return null;
        }

        isStartingRecording = false;

        if (Microphone.GetPosition(selectedDevice) <= 0)
        {
            if (Microphone.IsRecording(selectedDevice))
            {
                Microphone.End(selectedDevice);
            }

            recordingClip = null;
            isRecording = false;
            recordingStartedAt = -1f;
            UpdateStatus();
            yield break;
        }

        isRecording = true;
        UpdateStatus();
        // Notify receiver/UI that recording started
        Debug.Log("[AgentMicRecorder] Grabación iniciada.");
        if (receiver != null)
        {
            receiver.NotifyRecordingStarted();
        }
    }

    private void StopRecordingAndSend()
    {
        if (!isRecording) return;

        string selectedDevice = !string.IsNullOrWhiteSpace(activeMicrophoneDevice)
            ? activeMicrophoneDevice
            : ResolveMicrophoneDevice();

        int lastPos = Microphone.GetPosition(selectedDevice);
        Microphone.End(selectedDevice);
        isRecording = false;
        recordingStartedAt = -1f;
        UpdateStatus();

        // Notify receiver/UI that recording stopped and audio will be sent
        Debug.Log("[AgentMicRecorder] Grabación detenida. Preparando archivo y enviando...");
        if (receiver != null)
        {
            receiver.NotifyRecordingStoppedAndSent();
        }

        if (recordingClip == null)
        {
            Debug.LogError("No se produjo clip al grabar.");
            return;
        }

        // Crear nueva AudioClip con la longitud real
        float[] samples = new float[recordingClip.samples * recordingClip.channels];
        recordingClip.GetData(samples, 0);

        int channels = recordingClip.channels;
        int lengthSamples = Math.Min(lastPos * channels, samples.Length);
        if (lengthSamples <= 0)
        {
            Debug.LogError("La grabacion quedo vacia.");
            return;
        }

        float[] trimmed = new float[lengthSamples];
        Array.Copy(samples, 0, trimmed, 0, lengthSamples);

        int trimStart = 0;
        int trimEnd = trimmed.Length;
        float[] silenceTrimmed = trimSilence
            ? TrimSilence(trimmed, channels, sampleRate, silenceThreshold, silencePaddingMs, out trimStart, out trimEnd)
            : trimmed;

        byte[] wav = WavUtility.FromAudioClipData(silenceTrimmed, channels, sampleRate);
        string savedPath = SaveWavToSamplesFolder(wav, "agent_mic_recording");
        Debug.Log($"[AgentMicRecorder] Archivo WAV guardado en: {savedPath}");

        StartCoroutine(SendAudioCoroutine(wav));
    }

    private string SaveWavToSamplesFolder(byte[] wavBytes, string prefix)
    {
        string outputDirectory = Path.Combine(Application.dataPath, "Scripts", "SamplesWAV");
        if (!Directory.Exists(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        string fileName = $"{prefix}_{DateTime.Now:yyyyMMdd_HHmmss_fff}.wav";
        string outputPath = Path.Combine(outputDirectory, fileName);
        File.WriteAllBytes(outputPath, wavBytes);
        return outputPath;
    }

    private float[] TrimSilence(
        float[] samples,
        int channels,
        int sampleRateValue,
        float threshold,
        float paddingMilliseconds,
        out int trimStartSample,
        out int trimEndSample)
    {
        trimStartSample = 0;
        trimEndSample = samples.Length;

        if (samples.Length == 0 || channels <= 0)
        {
            return samples;
        }

        int paddingSamplesPerChannel = Mathf.Max(0, Mathf.RoundToInt((paddingMilliseconds / 1000f) * sampleRateValue));
        int firstSample = -1;
        int lastSample = -1;

        for (int i = 0; i < samples.Length; i++)
        {
            if (Mathf.Abs(samples[i]) >= threshold)
            {
                firstSample = i;
                break;
            }
        }

        for (int i = samples.Length - 1; i >= 0; i--)
        {
            if (Mathf.Abs(samples[i]) >= threshold)
            {
                lastSample = i;
                break;
            }
        }

        if (firstSample < 0 || lastSample < 0 || lastSample <= firstSample)
        {
            trimStartSample = 0;
            trimEndSample = samples.Length;
            return samples;
        }

        int paddedStart = Mathf.Max(0, firstSample - (paddingSamplesPerChannel * channels));
        int paddedEnd = Mathf.Min(samples.Length, lastSample + (paddingSamplesPerChannel * channels) + 1);

        trimStartSample = paddedStart;
        trimEndSample = paddedEnd;

        int length = Mathf.Max(0, paddedEnd - paddedStart);
        if (length <= 0)
        {
            return samples;
        }

        float[] output = new float[length];
        Array.Copy(samples, paddedStart, output, 0, length);
        return output;
    }

    public void RefreshMicrophones()
    {
        string[] devices = Microphone.devices;

        if (microphoneDropdown != null)
        {
            microphoneDropdown.ClearOptions();

            var options = new System.Collections.Generic.List<Dropdown.OptionData>();
            options.Add(new Dropdown.OptionData("Default"));

            foreach (string device in devices)
            {
                options.Add(new Dropdown.OptionData(device));
            }

            microphoneDropdown.AddOptions(options);

            int selectedIndex = 0;
            if (!string.IsNullOrWhiteSpace(microphoneDeviceName))
            {
                for (int i = 0; i < devices.Length; i++)
                {
                    if (string.Equals(devices[i], microphoneDeviceName, StringComparison.OrdinalIgnoreCase))
                    {
                        selectedIndex = i + 1;
                        break;
                    }
                }
            }

            microphoneDropdown.value = selectedIndex;
            microphoneDropdown.RefreshShownValue();
        }
    }

    private string ResolveMicrophoneDevice()
    {
        if (microphoneDropdown != null && microphoneDropdown.value > 0)
        {
            int selectedDeviceIndex = microphoneDropdown.value - 1;
            if (selectedDeviceIndex >= 0 && selectedDeviceIndex < Microphone.devices.Length)
            {
                return Microphone.devices[selectedDeviceIndex];
            }
        }

        if (!string.IsNullOrWhiteSpace(microphoneDeviceName))
        {
            foreach (string device in Microphone.devices)
            {
                if (string.Equals(device, microphoneDeviceName, StringComparison.OrdinalIgnoreCase))
                {
                    return device;
                }
            }

        }

        return Microphone.devices.Length > 0 ? Microphone.devices[0] : string.Empty;
    }

    private IEnumerator SendAudioCoroutine(byte[] wavBytes)
    {
        if (wavBytes == null || wavBytes.Length == 0)
        {
            Debug.LogError("Audio vacio, no se envia.");
            yield break;
        }

        var form = new WWWForm();
        form.AddBinaryData("file", wavBytes, "voice.wav", "audio/wav");
        form.AddField("user_id", userId);
        form.AddField("session_id", sessionId);
        form.AddField("tts_mode", ttsMode);
        string normalizedWorkflow = NormalizeWorkflow(workflow);
        Debug.Log($"[AgentMicRecorder] Sending workflow={normalizedWorkflow}");
        form.AddField("workflow", normalizedWorkflow);

        using (var www = UnityWebRequest.Post(transcribeUrl, form))
        {
            www.timeout = 60;
            yield return www.SendWebRequest();

            if (www.result != UnityWebRequest.Result.Success)
            {
                string err = www.error;
                Debug.LogError($"[AgentMicRecorder] Error enviando audio: {err}");
                receiver?.HandleError($"Error enviando audio: {err}");
                yield break;
            }

            string responseText = www.downloadHandler.text;

            if (debugLogPayloads)
            {
                Debug.Log($"[AgentMicRecorder] Response JSON: {responseText}");
            }

            BackendAgentResponse response = JsonUtility.FromJson<BackendAgentResponse>(responseText);
            if (response == null)
            {
                receiver?.HandleError("Respuesta inválida del backend tras transcribir.");
                yield break;
            }

            response.raw_json = responseText;
            HydrateResponseJsonFields(response, responseText);

            Debug.Log($"[AgentMicRecorder] Backend payload recibido:\n{responseText}");

            receiver?.HandleResponse(response);
        }
    }

    private void HydrateResponseJsonFields(BackendAgentResponse response, string rawJson)
    {
        if (response == null || string.IsNullOrWhiteSpace(rawJson))
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(response.state_json))
        {
            response.state_json = ExtractTopLevelString(rawJson, "state_json");
            if (string.IsNullOrWhiteSpace(response.state_json))
            {
                response.state_json = ExtractTopLevelObject(rawJson, "state");
            }
        }

        if (string.IsNullOrWhiteSpace(response.schedule_json))
        {
            response.schedule_json = ExtractTopLevelString(rawJson, "schedule_json");
            if (string.IsNullOrWhiteSpace(response.schedule_json))
            {
                response.schedule_json = ExtractTopLevelObject(rawJson, "schedule_report");
            }
        }

        if (string.IsNullOrWhiteSpace(response.output_json))
        {
            response.output_json = ExtractTopLevelString(rawJson, "output_json");
        }
    }

    private string ExtractTopLevelString(string json, string fieldName)
    {
        string pattern = $"\"{fieldName}\"";
        int keyIndex = json.IndexOf(pattern, StringComparison.Ordinal);
        if (keyIndex < 0)
        {
            return string.Empty;
        }

        int colonIndex = json.IndexOf(':', keyIndex + pattern.Length);
        if (colonIndex < 0)
        {
            return string.Empty;
        }

        int firstQuote = FindNextNonWhitespace(json, colonIndex + 1);
        if (firstQuote < 0 || json[firstQuote] != '"')
        {
            return string.Empty;
        }

        StringBuilder builder = new StringBuilder();
        bool escaping = false;

        for (int index = firstQuote + 1; index < json.Length; index++)
        {
            char current = json[index];
            if (escaping)
            {
                switch (current)
                {
                    case '"':
                    case '\\':
                    case '/':
                        builder.Append(current);
                        break;
                    case 'b':
                        builder.Append('\b');
                        break;
                    case 'f':
                        builder.Append('\f');
                        break;
                    case 'n':
                        builder.Append('\n');
                        break;
                    case 'r':
                        builder.Append('\r');
                        break;
                    case 't':
                        builder.Append('\t');
                        break;
                    case 'u':
                        if (index + 4 < json.Length)
                        {
                            string hex = json.Substring(index + 1, 4);
                            if (ushort.TryParse(hex, System.Globalization.NumberStyles.HexNumber, null, out ushort code))
                            {
                                builder.Append((char)code);
                                index += 4;
                            }
                        }
                        break;
                    default:
                        builder.Append(current);
                        break;
                }

                escaping = false;
                continue;
            }

            if (current == '\\')
            {
                escaping = true;
                continue;
            }

            if (current == '"')
            {
                return builder.ToString();
            }

            builder.Append(current);
        }

        return string.Empty;
    }

    private string ExtractTopLevelObject(string json, string fieldName)
    {
        string pattern = $"\"{fieldName}\"";
        int keyIndex = json.IndexOf(pattern, StringComparison.Ordinal);
        if (keyIndex < 0)
        {
            return string.Empty;
        }

        int colonIndex = json.IndexOf(':', keyIndex + pattern.Length);
        if (colonIndex < 0)
        {
            return string.Empty;
        }

        int objectStart = FindNextNonWhitespace(json, colonIndex + 1);
        if (objectStart < 0)
        {
            return string.Empty;
        }

        char opening = json[objectStart];
        char closing = opening == '{' ? '}' : opening == '[' ? ']' : '\0';
        if (closing == '\0')
        {
            return string.Empty;
        }

        int depth = 0;
        bool inString = false;
        bool escaping = false;

        for (int index = objectStart; index < json.Length; index++)
        {
            char current = json[index];

            if (inString)
            {
                if (escaping)
                {
                    escaping = false;
                }
                else if (current == '\\')
                {
                    escaping = true;
                }
                else if (current == '"')
                {
                    inString = false;
                }

                continue;
            }

            if (current == '"')
            {
                inString = true;
                continue;
            }

            if (current == opening)
            {
                depth++;
            }
            else if (current == closing)
            {
                depth--;
                if (depth == 0)
                {
                    return json.Substring(objectStart, index - objectStart + 1);
                }
            }
        }

        return string.Empty;
    }

    private int FindNextNonWhitespace(string text, int startIndex)
    {
        for (int index = startIndex; index < text.Length; index++)
        {
            if (!char.IsWhiteSpace(text[index]))
            {
                return index;
            }
        }

        return -1;
    }

    private string NormalizeWorkflow(string value)
    {
        string normalized = string.IsNullOrWhiteSpace(value) ? "schedule" : value.Trim().ToLowerInvariant();
        return normalized == "chat" ? "chat" : "schedule";
    }

    private void UpdateStatus()
    {
        UpdateRecordButtonVisual();

        if (statusText != null)
        {
            string deviceLabel = !string.IsNullOrWhiteSpace(activeMicrophoneDevice)
                ? activeMicrophoneDevice
                : ResolveMicrophoneDevice();

            statusText.text = isRecording
                ? $"Grabando... ({deviceLabel})"
                : $"Listo ({deviceLabel})";
        }
    }

    private void UpdateRecordButtonVisual()
    {
        if (recordButton == null)
        {
            return;
        }

        if (EventSystem.current != null && EventSystem.current.currentSelectedGameObject == recordButton.gameObject)
        {
            EventSystem.current.SetSelectedGameObject(null);
        }

        ColorBlock colors = hasCachedButtonColors ? cachedButtonColors : recordButton.colors;
        Color targetColor = isRecording || isStartingRecording
            ? colors.selectedColor
            : colors.normalColor;

        if (recordButton.targetGraphic is Graphic graphic)
        {
            ApplyGraphicColor(graphic, targetColor);
        }

        if (syncedToggleGraphics != null)
        {
            for (int index = 0; index < syncedToggleGraphics.Length; index++)
            {
                Graphic syncedGraphic = syncedToggleGraphics[index];
                if (syncedGraphic == null || syncedGraphic == recordButton.targetGraphic)
                {
                    continue;
                }

                ApplyGraphicColor(syncedGraphic, targetColor);
            }
        }
    }

    private void ResolveToggleGraphics()
    {
        if (recordButton == null)
        {
            return;
        }

        if (micBackgroundGraphic == null)
        {
            Transform micBgTransform = recordButton.transform.Find("MicBG");
            if (micBgTransform != null)
            {
                micBackgroundGraphic = micBgTransform.GetComponent<Graphic>();
            }
        }

        if (syncedToggleGraphics == null || syncedToggleGraphics.Length == 0)
        {
            if (micBackgroundGraphic != null)
            {
                syncedToggleGraphics = new[] { micBackgroundGraphic };
            }
            else if (recordButton.targetGraphic is Graphic targetGraphic)
            {
                syncedToggleGraphics = new[] { targetGraphic };
            }
        }
    }

    private void ResolveMicRing()
    {
        if (micRingImage != null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(micRingObjectName))
        {
            return;
        }

        GameObject ringObject = GameObject.Find(micRingObjectName);
        if (ringObject == null)
        {
            return;
        }

        micRingImage = ringObject.GetComponent<Image>();
    }

    private void UpdateMicRingVisual()
    {
        if (micRingImage == null)
        {
            ResolveMicRing();
        }

        if (micRingImage == null)
        {
            return;
        }

        bool isActive = isRecording || isStartingRecording;
        micRingImage.fillAmount = isActive ? RecordingProgressRatio : 0f;
    }

    private void ApplyGraphicColor(Graphic graphic, Color targetColor)
    {
        if (graphic == null)
        {
            return;
        }

        graphic.CrossFadeColor(targetColor, 0f, true, true);
        graphic.color = targetColor;
    }
}

// Helper WAV utility: convierte float[] PCM a wav bytes (16-bit PCM)
public static class WavUtility
{
    public static byte[] FromAudioClipData(float[] samples, int channels, int sampleRate)
    {
        // Convert float samples to 16-bit PCM
        short[] intData = new short[samples.Length];
        byte[] bytesData = new byte[samples.Length * 2];
        const float rescaleFactor = 32767; // to convert float to Int16

        for (int i = 0; i < samples.Length; i++)
        {
            float f = Mathf.Clamp(samples[i], -1f, 1f);
            short val = (short)(f * rescaleFactor);
            intData[i] = val;
            byte[] byteArr = BitConverter.GetBytes(val);
            bytesData[i * 2] = byteArr[0];
            bytesData[i * 2 + 1] = byteArr[1];
        }

        byte[] header = GetWavHeader(bytesData.Length, channels, sampleRate);
        byte[] wav = new byte[header.Length + bytesData.Length];
        Buffer.BlockCopy(header, 0, wav, 0, header.Length);
        Buffer.BlockCopy(bytesData, 0, wav, header.Length, bytesData.Length);
        return wav;
    }

    private static byte[] GetWavHeader(int dataLength, int channels, int sampleRate)
    {
        int byteRate = sampleRate * channels * 2;
        byte[] header = new byte[44];

        // ChunkID "RIFF"
        header[0] = (byte)'R'; header[1] = (byte)'I'; header[2] = (byte)'F'; header[3] = (byte)'F';
        // ChunkSize
        int fileSize = 36 + dataLength;
        BitConverter.GetBytes(fileSize).CopyTo(header, 4);
        // Format "WAVE"
        header[8] = (byte)'W'; header[9] = (byte)'A'; header[10] = (byte)'V'; header[11] = (byte)'E';
        // Subchunk1ID "fmt "
        header[12] = (byte)'f'; header[13] = (byte)'m'; header[14] = (byte)'t'; header[15] = (byte)' ';
        // Subchunk1Size (16 for PCM)
        BitConverter.GetBytes(16).CopyTo(header, 16);
        // AudioFormat (1 = PCM)
        BitConverter.GetBytes((short)1).CopyTo(header, 20);
        // NumChannels
        BitConverter.GetBytes((short)channels).CopyTo(header, 22);
        // SampleRate
        BitConverter.GetBytes(sampleRate).CopyTo(header, 24);
        // ByteRate
        BitConverter.GetBytes(byteRate).CopyTo(header, 28);
        // BlockAlign
        BitConverter.GetBytes((short)(channels * 2)).CopyTo(header, 32);
        // BitsPerSample
        BitConverter.GetBytes((short)16).CopyTo(header, 34);
        // Subchunk2ID "data"
        header[36] = (byte)'d'; header[37] = (byte)'a'; header[38] = (byte)'t'; header[39] = (byte)'a';
        // Subchunk2Size
        BitConverter.GetBytes(dataLength).CopyTo(header, 40);

        return header;
    }
}

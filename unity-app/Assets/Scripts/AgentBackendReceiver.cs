using System;
using TMPro;
using System.Linq;
using UnityEngine;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    public class AgentBackendReceiver : MonoBehaviour
    {
        [Header("UI Output")]
        [SerializeField] private TMP_Text statusText;
        [SerializeField] private TMP_Text chatText;
        [SerializeField] private TMP_Text stateText;
        [SerializeField] private TMP_Text warningsText;
        [SerializeField] private ScheduleGridCanvas scheduleGridCanvas;
        [SerializeField] private bool debugLogPayloads = false;

        [Header("Audio")]
        [SerializeField] private AgentAudioPlayer audioPlayer;

        [Header("Avatar Emotion")]
        [SerializeField] private AvatarEmotionDriver avatarEmotionDriver;

        public void HandleResponse(BackendAgentResponse response)
        {
            if (response == null)
            {
                HandleError("La respuesta del backend llego vacia.");
                return;
            }

            Debug.Log($"[AgentBackendReceiver] HandleResponse received. text={response.text}");

            if (chatText != null)
            {
                chatText.text = response.text ?? string.Empty;
            }

            // Mensaje público indicando que se recibió la respuesta hablada
            if (statusText != null)
            {
                statusText.text = $"Respuesta recibida: {response.text ?? string.Empty}";
            }

            if (stateText != null)
            {
                stateText.text = string.IsNullOrWhiteSpace(response.output_json)
                    ? "(sin output.json)"
                    : response.output_json;
            }

            if (debugLogPayloads)
            {
                if (!string.IsNullOrWhiteSpace(response.state_json))
                {
                    Debug.Log($"[AgentBackendReceiver] state_json: {response.state_json}");
                }

                if (!string.IsNullOrWhiteSpace(response.schedule_json))
                {
                    Debug.Log($"[AgentBackendReceiver] schedule_json: {response.schedule_json}");
                }
            }

            // Si el backend devolvió un state_json, actualizar paneles de estado
            try
            {
                if (!string.IsNullOrWhiteSpace(response.state_json))
                {
                    AgentStatePayload parsed = JsonUtility.FromJson<AgentStatePayload>(response.state_json);
                    // Actualizar el canvas de horarios con el estado (muestra cursos y restricciones)
                    if (scheduleGridCanvas != null)
                    {
                        scheduleGridCanvas.RenderFromStateJson(response.state_json);
                    }

                    if (parsed != null && parsed.draft != null && parsed.draft.courses != null && parsed.draft.courses.Length > 0)
                    {
                        var names = parsed.draft.courses.Select(c => c.course ?? string.Empty).Where(s => !string.IsNullOrWhiteSpace(s)).ToArray();
                        string joined = string.Join(", ", names);
                        Debug.Log($"[AgentBackendReceiver] Cursos añadidos detectados: {joined}");
                        if (scheduleGridCanvas == null && warningsText != null)
                        {
                            warningsText.text = $"Cursos añadidos: {joined}";
                        }
                    }
                }
            }
            catch (Exception)
            {
                // Ignorar errores de parsing
            }

            if (warningsText != null)
            {
                warningsText.text = string.Empty;
            }

            if (audioPlayer != null && !string.IsNullOrWhiteSpace(response.audio_base64))
            {
                audioPlayer.PlayFromBase64(response.audio_base64);
            }

            // Si el backend devolvió schedule_json, pasarla al canvas para renderizar el top3
            try
            {
                if (!string.IsNullOrWhiteSpace(response.schedule_json))
                {
                    if (scheduleGridCanvas != null)
                    {
                        Debug.Log("[AgentBackendReceiver] Schedule JSON recibido. Renderizando en canvas.");
                        scheduleGridCanvas.RenderFromScheduleJson(response.schedule_json);
                    }
                    else
                    {
                        // Fallback: mostrar en warningsText
                        Debug.Log("[AgentBackendReceiver] Schedule JSON recibido pero no hay canvas asignado.");
                        if (warningsText != null)
                        {
                            warningsText.text = "Horario generado (ver top 3 en canvas).";
                        }
                    }
                }
            }
            catch (Exception)
            {
                // Ignorar errores de parsing
            }

            if (avatarEmotionDriver == null)
            {
                avatarEmotionDriver = GetComponent<AvatarEmotionDriver>();
            }

            if (avatarEmotionDriver != null)
            {
                string selectedProfile = !string.IsNullOrWhiteSpace(response.emotion_profile)
                    ? response.emotion_profile
                    : !string.IsNullOrWhiteSpace(response.emotion)
                        ? response.emotion
                        : response.animation ?? string.Empty;

                avatarEmotionDriver.ApplyProfile(selectedProfile);
            }
        }

        public void HandleError(string message)
        {
            Debug.LogError($"[AgentBackendReceiver] {message}");

            if (statusText != null)
            {
                statusText.text = message;
            }

            if (warningsText != null)
            {
                warningsText.text = message;
            }

            if (avatarEmotionDriver == null)
            {
                avatarEmotionDriver = GetComponent<AvatarEmotionDriver>();
            }

            if (avatarEmotionDriver != null)
            {
                avatarEmotionDriver.ResetToNeutralImmediate();
            }
        }

        // Notificaciones de flujo de grabación
        public void NotifyRecordingStarted()
        {
            if (statusText != null)
            {
                statusText.text = "Grabación iniciada.";
            }
            else if (warningsText != null)
            {
                warningsText.text = "Grabación iniciada.";
            }
        }

        public void NotifyRecordingStoppedAndSent()
        {
            if (avatarEmotionDriver == null)
            {
                avatarEmotionDriver = GetComponent<AvatarEmotionDriver>();
            }

            if (avatarEmotionDriver != null)
            {
                avatarEmotionDriver.PlayThinkingLoop();
            }

            if (statusText != null)
            {
                statusText.text = "Grabación detenida y audio enviado.";
            }
            else if (warningsText != null)
            {
                warningsText.text = "Grabación detenida y audio enviado.";
            }
        }
    }

    [Serializable]
    public class BackendAgentResponse
    {
        public string text;
        public string audio_base64;
        public string emotion_profile;
        public string animation;
        public string emotion;
        public string[] warnings;
        public string state_json;
        public string schedule_json;
        public string output_json;
    }
}

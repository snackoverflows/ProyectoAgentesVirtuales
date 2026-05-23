using System;
using System.Collections;
using System.IO;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    [RequireComponent(typeof(AudioSource))]
    public class AgentAudioPlayer : MonoBehaviour
    {
        [SerializeField] private AudioSource audioSource;
        [SerializeField] private bool stopCurrentAudio = true;
        [SerializeField] private string temporaryFilePrefix = "agent_tts_response";

        private Coroutine activePlaybackCoroutine;

        private void Awake()
        {
            if (audioSource == null)
            {
                audioSource = GetComponent<AudioSource>();
            }
        }

        public void PlayFromBase64(string audioBase64)
        {
            if (string.IsNullOrWhiteSpace(audioBase64))
            {
                Debug.LogWarning("[AgentAudioPlayer] audio_base64 vacio.");
                return;
            }

            byte[] audioBytes;
            try
            {
                audioBytes = Convert.FromBase64String(audioBase64);
            }
            catch (Exception exception)
            {
                Debug.LogError($"[AgentAudioPlayer] No se pudo decodificar el audio base64: {exception.Message}");
                return;
            }

            if (activePlaybackCoroutine != null)
            {
                StopCoroutine(activePlaybackCoroutine);
                activePlaybackCoroutine = null;
            }

            activePlaybackCoroutine = StartCoroutine(LoadAndPlay(audioBytes));
        }

        private IEnumerator LoadAndPlay(byte[] audioBytes)
        {
            string fileName = $"{temporaryFilePrefix}_{DateTime.UtcNow.Ticks}.mp3";
            string tempPath = Path.Combine(Application.persistentDataPath, fileName);

            File.WriteAllBytes(tempPath, audioBytes);

            string fileUri = new Uri(Path.GetFullPath(tempPath)).AbsoluteUri;
            using (UnityWebRequest request = UnityWebRequestMultimedia.GetAudioClip(fileUri, AudioType.MPEG))
            {
                yield return request.SendWebRequest();

                if (request.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogError($"[AgentAudioPlayer] Error cargando audio: {request.error}");
                    TryDelete(tempPath);
                    activePlaybackCoroutine = null;
                    yield break;
                }

                AudioClip clip = DownloadHandlerAudioClip.GetContent(request);
                if (clip == null)
                {
                    Debug.LogError("[AgentAudioPlayer] No se pudo crear el AudioClip.");
                    TryDelete(tempPath);
                    activePlaybackCoroutine = null;
                    yield break;
                }

                if (stopCurrentAudio && audioSource != null && audioSource.isPlaying)
                {
                    audioSource.Stop();
                }

                if (audioSource != null)
                {
                    audioSource.clip = clip;
                    audioSource.Play();
                }
            }

            TryDelete(tempPath);
            activePlaybackCoroutine = null;
        }

        private void TryDelete(string path)
        {
            try
            {
                if (File.Exists(path))
                {
                    File.Delete(path);
                }
            }
            catch (Exception)
            {
                // Ignorar: el clip ya quedó cargado en memoria.
            }
        }
    }
}
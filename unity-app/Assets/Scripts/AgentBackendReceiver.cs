using System;
using System.Linq;
using TMPro;
using UnityEngine;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    public class AgentBackendReceiver : MonoBehaviour
    {
        [Header("UI Output")]
        [SerializeField] private TMP_Text statusText;
        [SerializeField] private TMP_Text chatText;
        [SerializeField] private TMP_Text stateText;
        [SerializeField] private TMP_Text scheduleText;
        [SerializeField] private TMP_Text warningsText;

        [Header("Schedule Grid")]
        [SerializeField] private ScheduleGridCanvas scheduleGridCanvas;

        [Header("Audio")]
        [SerializeField] private AgentAudioPlayer audioPlayer;

        public void HandleResponse(BackendAgentResponse response)
        {
            if (response == null)
            {
                HandleError("La respuesta del backend llego vacia.");
                return;
            }

            Debug.Log($"[AgentBackendReceiver] Chat: {response.text}");

            if (chatText != null)
            {
                chatText.text = response.text ?? string.Empty;
            }

            if (statusText != null)
            {
                statusText.text = $"{response.animation ?? ""} | {response.emotion ?? ""}".Trim(' ', '|');
            }

            if (stateText != null)
            {
                stateText.text = string.IsNullOrWhiteSpace(response.state_json)
                    ? "(sin output.json)"
                    : response.state_json;
            }

            if (scheduleText != null)
            {
                scheduleText.text = string.IsNullOrWhiteSpace(response.schedule_json)
                    ? "(sin schedule.json)"
                    : response.schedule_json;
            }

            if (scheduleGridCanvas == null)
            {
                scheduleGridCanvas = GetComponent<ScheduleGridCanvas>();
            }

            if (scheduleGridCanvas != null)
            {
                scheduleGridCanvas.RenderFromStateJson(response.state_json);
            }

            if (scheduleGridCanvas != null)
            {
                scheduleGridCanvas.RenderFromScheduleJson(response.schedule_json);
            }

            if (warningsText != null)
            {
                warningsText.text = response.warnings == null || response.warnings.Length == 0
                    ? "Sin warnings"
                    : string.Join("\n", response.warnings);
            }

            if (audioPlayer != null && !string.IsNullOrWhiteSpace(response.audio_base64))
            {
                audioPlayer.PlayFromBase64(response.audio_base64);
            }

            if (!string.IsNullOrWhiteSpace(response.state_json))
            {
                Debug.Log($"[AgentBackendReceiver] output.json-like:\n{response.state_json}");
            }

            if (!string.IsNullOrWhiteSpace(response.schedule_json))
            {
                Debug.Log($"[AgentBackendReceiver] schedule.json-like:\n{response.schedule_json}");
            }

            if (response.warnings != null && response.warnings.Length > 0)
            {
                Debug.LogWarning($"[AgentBackendReceiver] Warnings: {string.Join(" | ", response.warnings.Where(item => !string.IsNullOrWhiteSpace(item)))}");
            }
        }

        public void HandleError(string message)
        {
            Debug.LogError($"[AgentBackendReceiver] {message}");

            if (scheduleGridCanvas == null)
            {
                scheduleGridCanvas = GetComponent<ScheduleGridCanvas>();
            }

            if (scheduleGridCanvas != null)
            {
                scheduleGridCanvas.RenderFromStateJson(string.Empty);
                scheduleGridCanvas.RenderFromScheduleJson(string.Empty);
            }

            if (statusText != null)
            {
                statusText.text = message;
            }

            if (warningsText != null)
            {
                warningsText.text = message;
            }
        }
    }
}

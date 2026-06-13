using System;
using UnityEngine;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    public class AgentBackendReceiver : MonoBehaviour
    {
        [Header("Schedule UI")]
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
            LogBackendPayload(response);

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

            try
            {
                if (scheduleGridCanvas != null)
                {
                    EnsureScheduleGridCanvasIsActive();

                    if (response.state != null)
                    {
                        scheduleGridCanvas.RenderFromStatePayload(response.state);
                    }
                    else
                    {
                        string stateJson = GetStateJson(response);
                        if (!string.IsNullOrWhiteSpace(stateJson))
                        {
                            scheduleGridCanvas.RenderFromStateJson(stateJson);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[AgentBackendReceiver] Error renderizando state: {ex}");
            }

            if (audioPlayer != null && !string.IsNullOrWhiteSpace(response.audio_base64))
            {
                audioPlayer.PlayFromBase64(response.audio_base64);
            }

            try
            {
                if (scheduleGridCanvas != null)
                {
                    EnsureScheduleGridCanvasIsActive();

                    if (response.schedule_report != null)
                    {
                        Debug.Log("[AgentBackendReceiver] Schedule payload recibido. Renderizando en canvas.");
                        scheduleGridCanvas.RenderFromSchedulePayload(response.schedule_report);
                    }
                    else
                    {
                        string scheduleJson = GetScheduleJson(response);
                        if (!string.IsNullOrWhiteSpace(scheduleJson))
                        {
                            Debug.Log("[AgentBackendReceiver] Schedule JSON recibido. Renderizando en canvas.");
                            scheduleGridCanvas.RenderFromScheduleJson(scheduleJson);
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[AgentBackendReceiver] Error renderizando schedule: {ex}");
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

        private void LogBackendPayload(BackendAgentResponse response)
        {
            if (response == null)
            {
                return;
            }

            if (!string.IsNullOrWhiteSpace(response.raw_json))
            {
                Debug.Log($"[AgentBackendReceiver] Backend raw payload:\n{SanitizePayloadForLog(response.raw_json)}");
                return;
            }

            if (!string.IsNullOrWhiteSpace(response.output_json))
            {
                Debug.Log($"[AgentBackendReceiver] Backend payload:\n{response.output_json}");
                return;
            }

            string stateJson = GetStateJson(response);
            string scheduleJson = GetScheduleJson(response);
            Debug.Log(
                "[AgentBackendReceiver] Backend payload (fallback):\n"
                + "{\n"
                + $"  \"text\": \"{EscapeForLog(response.text)}\",\n"
                + $"  \"emotion_profile\": \"{EscapeForLog(response.emotion_profile)}\",\n"
                + $"  \"state_json\": \"{EscapeForLog(stateJson)}\",\n"
                + $"  \"schedule_json\": \"{EscapeForLog(scheduleJson)}\"\n"
                + "}"
            );
        }

        private string SanitizePayloadForLog(string rawJson)
        {
            if (string.IsNullOrWhiteSpace(rawJson))
            {
                return string.Empty;
            }

            const string fieldName = "\"audio_base64\"";
            int keyIndex = rawJson.IndexOf(fieldName, StringComparison.Ordinal);
            if (keyIndex < 0)
            {
                return rawJson;
            }

            int colonIndex = rawJson.IndexOf(':', keyIndex + fieldName.Length);
            if (colonIndex < 0)
            {
                return rawJson;
            }

            int valueStart = FindNextNonWhitespace(rawJson, colonIndex + 1);
            if (valueStart < 0 || rawJson[valueStart] != '"')
            {
                return rawJson;
            }

            int valueEnd = FindStringEnd(rawJson, valueStart);
            if (valueEnd < 0)
            {
                return rawJson;
            }

            return rawJson.Substring(0, valueStart + 1)
                + "<omitted>"
                + rawJson.Substring(valueEnd);
        }

        private string EscapeForLog(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n");
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

        private int FindStringEnd(string text, int openingQuoteIndex)
        {
            bool escaping = false;
            for (int index = openingQuoteIndex + 1; index < text.Length; index++)
            {
                char current = text[index];
                if (escaping)
                {
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
                    return index;
                }
            }

            return -1;
        }

        private void EnsureScheduleGridCanvasIsActive()
        {
            if (scheduleGridCanvas != null && !scheduleGridCanvas.gameObject.activeSelf)
            {
                scheduleGridCanvas.gameObject.SetActive(true);
            }
        }

        private static string GetStateJson(BackendAgentResponse response)
        {
            if (response == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(response.state_json))
            {
                return response.state_json;
            }

            if (response.state != null && response.state.draft != null)
            {
                return JsonUtility.ToJson(response.state);
            }

            return string.Empty;
        }

        private static string GetScheduleJson(BackendAgentResponse response)
        {
            if (response == null)
            {
                return string.Empty;
            }

            if (!string.IsNullOrWhiteSpace(response.schedule_json))
            {
                return response.schedule_json;
            }

            if (response.schedule_report != null && response.schedule_report.schedules != null && response.schedule_report.schedules.Length > 0)
            {
                return JsonUtility.ToJson(response.schedule_report);
            }

            return string.Empty;
        }

        public void HandleError(string message)
        {
            Debug.LogError($"[AgentBackendReceiver] {message}");

            if (avatarEmotionDriver == null)
            {
                avatarEmotionDriver = GetComponent<AvatarEmotionDriver>();
            }

            if (avatarEmotionDriver != null)
            {
                avatarEmotionDriver.ResetToNeutralImmediate();
            }
        }

        public void NotifyRecordingStarted()
        {
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
        public BackendStatePayload state;
        public BackendScheduleReportPayload schedule_report;
        public string state_json;
        public string schedule_json;
        public string output_json;
        public string raw_json;
    }

    [Serializable]
    public class BackendStatePayload
    {
        public string assistant_message;
        public BackendDraftPayload draft;
        public string status;
        public string[] missing_items;
        public bool should_generate;
        public string emotion_profile;
    }

    [Serializable]
    public class BackendDraftPayload
    {
        public BackendCoursePayload[] courses;
        public BackendConstraintsPayload constraints;
    }

    [Serializable]
    public class BackendCoursePayload
    {
        public string course;
        public string group;
        public string professor;
        public BackendMeetingPayload[] meetings;
    }

    [Serializable]
    public class BackendMeetingPayload
    {
        public string day;
        public string start;
        public string end;
    }

    [Serializable]
    public class BackendConstraintsPayload
    {
        public BackendRulePayload[] hard;
        public BackendRulePayload[] soft;
        public BackendOptimizationPayload optimization;
        public BackendScoringPayload scoring;
    }

    [Serializable]
    public class BackendRulePayload
    {
        public string type;
        public string scope;
        public string @operator;
        public string reason;
        public string target;
        public string category;
        public string preference_level;
        public int value;
        public string[] days;
        public AgentTimeRange range;
        public string[] values;
    }

    [Serializable]
    public class BackendOptimizationPayload
    {
        public BackendObjectivePayload[] objectives;
    }

    [Serializable]
    public class BackendObjectivePayload
    {
        public string @operator;
        public string target;
        public int priority;
        public int weight;
        public string reason;
        public string aggregation;
    }

    [Serializable]
    public class BackendScoringPayload
    {
        public string mode;
        public int per;
    }

    [Serializable]
    public class BackendScheduleReportPayload
    {
        public string text;
        public BackendSchedulePayload[] schedules;
        public string[] warnings;
        public BackendExecutionParamsPayload execution_params;
    }

    [Serializable]
    public class BackendSchedulePayload
    {
        public BackendScheduleMetaPayload meta;
        public BackendBlockPayload[] blocks;
    }

    [Serializable]
    public class BackendScheduleMetaPayload
    {
        public int raw_score;
        public int user_score;
        public BackendUserScoreBreakdownPayload user_score_breakdown;
        public int distinct_courses;
        public int distinct_days;
    }

    [Serializable]
    public class BackendUserScoreBreakdownPayload
    {
        public float coverage_ratio;
        public float day_efficiency;
        public float soft_ratio;
    }

    [Serializable]
    public class BackendBlockPayload
    {
        public string day;
        public string start;
        public string end;
        public string course;
        public string group;
        public string professor;
        public string[] tags;
    }

    [Serializable]
    public class BackendExecutionParamsPayload
    {
        public int max_per_day;
        public string max_per_day_source;
        public int top_n;
        public string top_n_source;
    }
}

using System;
using System.Collections;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    [Serializable]
    public class BackendAgentRequest
    {
        public string content;
        public string user_id = "unity_user";
        public string session_id = "default";
        public string tts_mode = "auto";
        public string workflow = "schedule";
    }

    [Serializable]
    public class BackendAgentResponse
    {
        public string text;
        public string audio_base64;
        public string animation;
        public string emotion;
        public string[] warnings;
        public string state_json;
        public string schedule_json;
    }

    public class AgentBackendSender : MonoBehaviour
    {
        [Header("Backend")]
        [SerializeField] private string backendUrl = "http://127.0.0.1:8000/agent";
        [SerializeField] private string workflow = "schedule";
        [SerializeField] private string userId = "unity_user";
        [SerializeField] private string sessionId = "default";
        [SerializeField] private string ttsMode = "auto";

        [Header("UI")]
        [SerializeField] private TMP_InputField inputField;
        [SerializeField] private Button sendButton;
        [SerializeField] private AgentBackendReceiver receiver;
        [SerializeField] private bool clearInputAfterSend = true;

        private Coroutine activeRequestCoroutine;
        private UnityWebRequest activeRequest;

        private void OnEnable()
        {
            if (sendButton != null)
            {
                sendButton.onClick.RemoveListener(SendCurrentInput);
                sendButton.onClick.AddListener(SendCurrentInput);
            }
        }

        private void OnDisable()
        {
            if (sendButton != null)
            {
                sendButton.onClick.RemoveListener(SendCurrentInput);
            }

            if (activeRequestCoroutine != null)
            {
                StopCoroutine(activeRequestCoroutine);
                activeRequestCoroutine = null;
            }

            if (activeRequest != null)
            {
                activeRequest.Abort();
                activeRequest.Dispose();
                activeRequest = null;
            }
        }

        private void OnDestroy()
        {
            if (sendButton != null)
            {
                sendButton.onClick.RemoveListener(SendCurrentInput);
            }

            if (activeRequest != null)
            {
                activeRequest.Abort();
                activeRequest.Dispose();
                activeRequest = null;
            }
        }

        public void SendCurrentInput()
        {
            if (inputField == null)
            {
                Debug.LogError("[AgentBackendSender] No se asigno un TMP_InputField.");
                return;
            }

            string content = inputField.text;
            Debug.Log($"[AgentBackendSender] Boton presionado. Enviando: {content}");

            if (clearInputAfterSend)
            {
                inputField.text = string.Empty;
                inputField.ActivateInputField();
            }

            SendText(content);
        }

        public void SendText(string content)
        {
            Debug.Log($"[AgentBackendSender] SendText llamado. Longitud={content?.Length ?? 0}");

            if (activeRequestCoroutine != null)
            {
                StopCoroutine(activeRequestCoroutine);
                activeRequestCoroutine = null;
            }

            activeRequestCoroutine = StartCoroutine(SendRequest(content));
        }

        private IEnumerator SendRequest(string content)
        {
            if (string.IsNullOrWhiteSpace(content))
            {
                activeRequestCoroutine = null;
                receiver?.HandleError("No hay texto para enviar.");
                yield break;
            }

            var payload = new BackendAgentRequest
            {
                content = content,
                user_id = userId,
                session_id = sessionId,
                tts_mode = ttsMode,
                workflow = workflow,
            };

            string requestJson = JsonUtility.ToJson(payload);
            using (var request = new UnityWebRequest(backendUrl, UnityWebRequest.kHttpVerbPOST))
            {
                activeRequest = request;
                request.disposeUploadHandlerOnDispose = true;
                request.disposeDownloadHandlerOnDispose = true;
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(requestJson));
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "application/json");

                yield return request.SendWebRequest();

                activeRequest = null;

                if (request.result != UnityWebRequest.Result.Success)
                {
                    string errorMessage = $"Error al conectar con el backend: {request.error}";
                    Debug.LogError($"[AgentBackendSender] {errorMessage}");
                    activeRequestCoroutine = null;
                    receiver?.HandleError(errorMessage);
                    yield break;
                }

                string responseText = request.downloadHandler.text;
                Debug.Log($"[AgentBackendSender] Respuesta cruda: {responseText}");
                BackendAgentResponse response = JsonUtility.FromJson<BackendAgentResponse>(responseText);
                if (response == null)
                {
                    string errorMessage = "No se pudo deserializar la respuesta del backend.";
                    Debug.LogError($"[AgentBackendSender] {errorMessage}\n{responseText}");
                    activeRequestCoroutine = null;
                    receiver?.HandleError(errorMessage);
                    yield break;
                }

                receiver?.HandleResponse(response);
            }

            activeRequestCoroutine = null;
        }
    }
}

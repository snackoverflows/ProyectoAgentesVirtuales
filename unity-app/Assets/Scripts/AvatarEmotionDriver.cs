using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    [Serializable]
    public class BlendShapeEmotionTarget
    {
        public string blendShapeName = "nii";
        [Range(0f, 100f)]
        public float weight = 35f;
        public bool isMouthBlendShape = false;
    }

    [Serializable]
    public class EmotionAnimationProfile
    {
        public string emotion = "neutral";
        public string animationState = "Idle";
        public float durationSeconds = 2.2f;
        public BlendShapeEmotionTarget[] blendShapes = Array.Empty<BlendShapeEmotionTarget>();
    }

    public class AvatarEmotionDriver : MonoBehaviour
    {
        [Header("Avatar Refs")]
        [SerializeField] private Animator animator;
        [SerializeField] private SkinnedMeshRenderer faceRenderer;
        [SerializeField] private string fallbackFaceChildNameContains = "body";

        [Header("Audio / LipSync")]
        [SerializeField] private AgentAudioPlayer audioPlayer;
        [SerializeField] private AudioSource audioSource;
        [SerializeField] private bool blockMouthBlendShapesWhileSpeaking = true;

        [Header("Animation Defaults")]
        [SerializeField] private string idleStateName = "Idle";
        [SerializeField] private float crossFadeSeconds = 0.12f;

        [Header("Hardcoded Profiles (Phase 1)")]
        [SerializeField] private EmotionAnimationProfile[] emotionProfiles =
        {
            new EmotionAnimationProfile
            {
                emotion = "neutral",
                animationState = "Idle",
                durationSeconds = 0f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            },
            new EmotionAnimationProfile
            {
                emotion = "friendly",
                animationState = "Idle",
                durationSeconds = 0f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            },
            new EmotionAnimationProfile
            {
                emotion = "thinking",
                animationState = "Thinking",
                durationSeconds = 0f,
                blendShapes = new[]
                {
                    new BlendShapeEmotionTarget
                    {
                        blendShapeName = "nii",
                        weight = 35f,
                        isMouthBlendShape = false
                    }
                }
            },
            new EmotionAnimationProfile
            {
                emotion = "sad",
                animationState = "Sad",
                durationSeconds = 2.2f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            },
            new EmotionAnimationProfile
            {
                emotion = "surprise",
                animationState = "Surprise",
                durationSeconds = 1.8f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            },
            new EmotionAnimationProfile
            {
                emotion = "happy",
                animationState = "Victory",
                durationSeconds = 2.2f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            },
            new EmotionAnimationProfile
            {
                emotion = "point_lu",
                animationState = "PointLU",
                durationSeconds = 1.6f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            },
            new EmotionAnimationProfile
            {
                emotion = "point_ru",
                animationState = "PointRU",
                durationSeconds = 1.6f,
                blendShapes = Array.Empty<BlendShapeEmotionTarget>()
            }
        };

        private readonly Dictionary<string, EmotionAnimationProfile> profileByEmotion = new Dictionary<string, EmotionAnimationProfile>(StringComparer.OrdinalIgnoreCase);
        private readonly Dictionary<int, float> baseBlendShapeWeights = new Dictionary<int, float>();

        private Coroutine resetRoutine;

        private void Awake()
        {
            ResolveReferences();
            RebuildProfilesCache();
            CacheBaseBlendShapeWeights();
            ResetToNeutralImmediate();
        }

        public void ApplyProfile(string emotionProfile)
        {
            string normalizedEmotion = NormalizeKey(emotionProfile);

            if (!profileByEmotion.TryGetValue(normalizedEmotion, out EmotionAnimationProfile profile))
            {
                profile = profileByEmotion.TryGetValue("neutral", out EmotionAnimationProfile neutralProfile)
                    ? neutralProfile
                    : null;
            }

            if (profile == null)
            {
                PlayAnimationIfPossible(idleStateName);
                return;
            }

            if (resetRoutine != null)
            {
                StopCoroutine(resetRoutine);
                resetRoutine = null;
            }

            string targetState = profile.animationState;
            if (string.IsNullOrWhiteSpace(targetState))
            {
                targetState = idleStateName;
            }

            PlayAnimationIfPossible(targetState);
            ApplyBlendShapes(profile.blendShapes);

            if (profile.durationSeconds > 0f)
            {
                resetRoutine = StartCoroutine(ReturnToNeutralAfter(profile.durationSeconds));
            }
        }

        public void PlayThinkingLoop()
        {
            ApplyProfile("thinking");
        }

        public void ApplyFromMetadata(string animation, string emotion)
        {
            string profile = !string.IsNullOrWhiteSpace(emotion) ? emotion : animation;
            ApplyProfile(profile);
        }

        public void ResetToNeutralImmediate()
        {
            if (resetRoutine != null)
            {
                StopCoroutine(resetRoutine);
                resetRoutine = null;
            }

            PlayAnimationIfPossible(idleStateName);
            RestoreBaseBlendShapeWeights();
        }

        private IEnumerator ReturnToNeutralAfter(float delaySeconds)
        {
            yield return new WaitForSeconds(delaySeconds);
            PlayAnimationIfPossible(idleStateName);
            RestoreBaseBlendShapeWeights();
            resetRoutine = null;
        }

        private void ResolveReferences()
        {
            if (animator == null)
            {
                animator = GetComponentInChildren<Animator>(true);
            }

            if (audioPlayer == null)
            {
                audioPlayer = GetComponent<AgentAudioPlayer>();
                if (audioPlayer == null)
                {
                    audioPlayer = FindAnyObjectByType<AgentAudioPlayer>();
                }
            }

            if (audioSource == null && audioPlayer != null)
            {
                audioSource = audioPlayer.AudioSource;
            }

            if (faceRenderer == null)
            {
                faceRenderer = FindFaceRenderer();
            }
        }

        private SkinnedMeshRenderer FindFaceRenderer()
        {
            SkinnedMeshRenderer[] renderers = GetComponentsInChildren<SkinnedMeshRenderer>(true);
            if (renderers == null || renderers.Length == 0)
            {
                return null;
            }

            if (!string.IsNullOrWhiteSpace(fallbackFaceChildNameContains))
            {
                string key = fallbackFaceChildNameContains.Trim();
                SkinnedMeshRenderer byName = renderers.FirstOrDefault(renderer =>
                    renderer != null && renderer.name.IndexOf(key, StringComparison.OrdinalIgnoreCase) >= 0);
                if (byName != null)
                {
                    return byName;
                }
            }

            return renderers[0];
        }

        private void RebuildProfilesCache()
        {
            profileByEmotion.Clear();

            if (emotionProfiles == null)
            {
                return;
            }

            foreach (EmotionAnimationProfile profile in emotionProfiles)
            {
                if (profile == null)
                {
                    continue;
                }

                string key = NormalizeKey(profile.emotion);
                if (string.IsNullOrWhiteSpace(key))
                {
                    continue;
                }

                profileByEmotion[key] = profile;
            }
        }

        private void CacheBaseBlendShapeWeights()
        {
            baseBlendShapeWeights.Clear();

            if (faceRenderer == null || faceRenderer.sharedMesh == null)
            {
                return;
            }

            int blendShapeCount = faceRenderer.sharedMesh.blendShapeCount;
            for (int i = 0; i < blendShapeCount; i++)
            {
                baseBlendShapeWeights[i] = faceRenderer.GetBlendShapeWeight(i);
            }
        }

        private void ApplyBlendShapes(BlendShapeEmotionTarget[] targets)
        {
            RestoreBaseBlendShapeWeights();

            if (faceRenderer == null || faceRenderer.sharedMesh == null || targets == null)
            {
                return;
            }

            bool speaking = IsSpeaking();

            foreach (BlendShapeEmotionTarget target in targets)
            {
                if (target == null || string.IsNullOrWhiteSpace(target.blendShapeName))
                {
                    continue;
                }

                if (speaking && blockMouthBlendShapesWhileSpeaking && target.isMouthBlendShape)
                {
                    continue;
                }

                int index = faceRenderer.sharedMesh.GetBlendShapeIndex(target.blendShapeName.Trim());
                if (index < 0)
                {
                    continue;
                }

                faceRenderer.SetBlendShapeWeight(index, Mathf.Clamp(target.weight, 0f, 100f));
            }
        }

        private void RestoreBaseBlendShapeWeights()
        {
            if (faceRenderer == null || faceRenderer.sharedMesh == null)
            {
                return;
            }

            bool speaking = IsSpeaking();

            foreach (KeyValuePair<int, float> pair in baseBlendShapeWeights)
            {
                int index = pair.Key;
                float weight = pair.Value;

                if (speaking && blockMouthBlendShapesWhileSpeaking && IsLikelyMouthBlendShape(index))
                {
                    continue;
                }

                faceRenderer.SetBlendShapeWeight(index, Mathf.Clamp(weight, 0f, 100f));
            }
        }

        private bool IsLikelyMouthBlendShape(int index)
        {
            if (faceRenderer == null || faceRenderer.sharedMesh == null || index < 0)
            {
                return false;
            }

            string name = faceRenderer.sharedMesh.GetBlendShapeName(index);
            if (string.IsNullOrWhiteSpace(name))
            {
                return false;
            }

            string lowered = name.ToLowerInvariant();
            return lowered.Contains("mouth") || lowered.Contains("lip") || lowered.Contains("jaw") ||
                   lowered == "a" || lowered == "i" || lowered == "u" || lowered == "e" || lowered == "o";
        }

        private bool IsSpeaking()
        {
            if (audioSource != null)
            {
                return audioSource.isPlaying;
            }

            return audioPlayer != null && audioPlayer.IsPlaying;
        }

        private void PlayAnimationIfPossible(string stateName)
        {
            if (animator == null || string.IsNullOrWhiteSpace(stateName))
            {
                return;
            }

            int stateHash = Animator.StringToHash(stateName);
            if (animator.HasState(0, stateHash))
            {
                animator.CrossFade(stateHash, crossFadeSeconds, 0);
                return;
            }

            if (!string.Equals(stateName, idleStateName, StringComparison.OrdinalIgnoreCase))
            {
                int idleHash = Animator.StringToHash(idleStateName);
                if (animator.HasState(0, idleHash))
                {
                    animator.CrossFade(idleHash, crossFadeSeconds, 0);
                }
            }
        }

        private static string NormalizeKey(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "neutral" : value.Trim().ToLowerInvariant();
        }
    }
}

using System;
using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace ProyectoAgentesVirtuales.UnityBridge
{
    [Serializable]
    public class ScheduleReportPayload
    {
        public string text;
        public ScheduleEntry[] schedules;
        public string[] warnings;
    }

    [Serializable]
    public class ScheduleEntry
    {
        public ScheduleMeta meta;
        public ScheduleBlock[] blocks;
    }

    [Serializable]
    public class ScheduleMeta
    {
        public int raw_score;
        public int distinct_courses;
        public int distinct_days;
    }

    [Serializable]
    public class AgentStatePayload
    {
        public AgentDraftPayload draft;
    }

    [Serializable]
    public class AgentDraftPayload
    {
        public AgentCoursePayload[] courses;
        public AgentConstraintsPayload constraints;
    }

    [Serializable]
    public class AgentCoursePayload
    {
        public string course;
        public string group;
        public string professor;
        public AgentCourseMeetingPayload[] meetings;
        public string[] tags;
    }

    [Serializable]
    public class AgentCourseMeetingPayload
    {
        public string day;
        public string start;
        public string end;
    }

    [Serializable]
    public class AgentConstraintsPayload
    {
        public AgentConstraintRule[] hard;
        public AgentConstraintRule[] soft;
        public AgentOptimizationPayload optimization;
        public AgentScoringPayload scoring;
    }

    [Serializable]
    public class AgentConstraintRule
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
    public class AgentTimeRange
    {
        public string start;
        public string end;
    }

    [Serializable]
    public class AgentOptimizationPayload
    {
        public AgentObjectivePayload[] objectives;
    }

    [Serializable]
    public class AgentObjectivePayload
    {
        public string @operator;
        public string target;
        public int weight;
        public int priority;
        public string aggregation;
    }

    [Serializable]
    public class AgentScoringPayload
    {
        public string mode;
        public int per;
    }

    [Serializable]
    public class ScheduleBlock
    {
        public string day;
        public string start;
        public string end;
        public string course;
        public string group;
        public string professor;
        public string[] tags;
    }

    public class ScheduleGridCanvas : MonoBehaviour
    {
        [Header("Canvas")]
        [SerializeField] private Canvas targetCanvas;
        [SerializeField] private bool createCanvasIfMissing = true;
        [SerializeField] private Vector2 canvasSize = new Vector2(1650f, 920f);
        [SerializeField] private bool showGridByDefault = false;
        [SerializeField] private bool showConstraintsByDefault = false;
        [SerializeField] private bool showCoursesByDefault = false;

        [Header("Grid")]
        [SerializeField] private int startHour = 7;
        [SerializeField] private int endHour = 23;
        [SerializeField] private float dayColumnWidth = 170f;
        [SerializeField] private float hourColumnWidth = 92f;
        [SerializeField] private float rowHeight = 44f;
        [SerializeField] private float rowSpacing = 10f;
        [SerializeField] private float cellSpacing = 8f;
        [SerializeField] private Vector4 contentPadding = new Vector4(28f, 24f, 28f, 28f);
        [SerializeField] private Vector2 titleSpacing = new Vector2(0f, 10f);
        [SerializeField] private Vector2 subtitleSpacing = new Vector2(0f, 14f);
        [SerializeField] private Vector2 gridTopSpacing = new Vector2(0f, 12f);
        [SerializeField] private float gridHorizontalPadding = 150f;
        [SerializeField] private float titleHeight = 42f;
        [SerializeField] private float subtitleHeight = 28f;
        [SerializeField] private int maxVisibleSchedules = 3;
        [SerializeField] private float controlButtonWidth = 160f;
        [SerializeField] private float controlButtonHeight = 42f;
        [SerializeField] private float controlButtonSpacing = 10f;
        [SerializeField] private Vector2 controlsOffset = new Vector2(20f, 20f);
        [SerializeField] private float constraintsPanelWidth = 560f;
        [SerializeField] private float constraintsPanelHeight = 320f;
        [SerializeField] private Vector2 constraintsPanelOffset = new Vector2(20f, 78f);
        [SerializeField] private float coursesPanelWidth = 680f;
        [SerializeField] private float coursesPanelHeight = 360f;
        [SerializeField] private Vector2 coursesPanelOffset = new Vector2(600f, 78f);

        [Header("Colors")]
        [SerializeField] private Color boardBackground = new Color(0.13f, 0.14f, 0.18f, 0.96f);
        [SerializeField] private Color headerBackground = new Color(0.22f, 0.24f, 0.30f, 1f);
        [SerializeField] private Color hourBackground = new Color(0.18f, 0.19f, 0.24f, 1f);
        [SerializeField] private Color emptySlotBackground = new Color(0.16f, 0.17f, 0.21f, 0.95f);
        [SerializeField] private Color filledSlotBackground = new Color(0.23f, 0.45f, 0.74f, 0.96f);
        [SerializeField] private Color filledSlotText = Color.white;
        [SerializeField] private Color emptySlotText = new Color(0.88f, 0.90f, 0.94f, 0.75f);

        private RectTransform rootPanel;
        private RectTransform controlsLeftPanel;
        private RectTransform controlsRightPanel;
        private RectTransform scheduleNavPanel;
        private RectTransform constraintsPanel;
        private RectTransform coursesPanel;
        private RectTransform gridRoot;
        private TMP_Text titleText;
        private TMP_Text subtitleText;
        private TMP_Text toggleButtonLabel;
        private TMP_Text previousButtonLabel;
        private TMP_Text nextButtonLabel;
        private TMP_Text pageLabel;
        private TMP_Text constraintsButtonLabel;
        private TMP_Text constraintsText;
        private TMP_Text coursesButtonLabel;
        private TMP_Text coursesText;
        private Button toggleButton;
        private Button previousButton;
        private Button nextButton;
        private Button constraintsButton;
        private Button coursesButton;
        private readonly Dictionary<string, Dictionary<int, SlotCell>> slotCells = new Dictionary<string, Dictionary<int, SlotCell>>(StringComparer.OrdinalIgnoreCase);
        private bool gridBuilt;
        private bool gridVisible;
        private bool constraintsVisible;
        private bool coursesVisible;
        private ScheduleReportPayload currentReport;
        private int currentScheduleIndex;
        private AgentStatePayload currentState;

        private class SlotCell
        {
            public Image Background;
            public TMP_Text Label;
        }

        private static readonly string[] OrderedDays =
        {
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        };

        private static readonly Dictionary<string, string> DayAliases = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
        {
            { "monday", "Lunes" },
            { "tuesday", "Martes" },
            { "wednesday", "Miércoles" },
            { "thursday", "Jueves" },
            { "friday", "Viernes" },
            { "saturday", "Sábado" },
            { "sunday", "Domingo" },
            { "lunes", "Lunes" },
            { "martes", "Martes" },
            { "miercoles", "Miércoles" },
            { "miércoles", "Miércoles" },
            { "jueves", "Jueves" },
            { "viernes", "Viernes" },
            { "sabado", "Sábado" },
            { "sábado", "Sábado" },
            { "domingo", "Domingo" },
        };

        private void Awake()
        {
            EnsureCanvas();
            BuildControls();
            BuildConstraintsPanel();
            BuildCoursesPanel();
            BuildEmptyGrid();
            SetGridVisible(showGridByDefault);
            SetConstraintsVisible(showConstraintsByDefault);
            SetCoursesVisible(showCoursesByDefault);
        }

        public void RenderFromScheduleJson(string scheduleJson)
        {
            EnsureCanvas();
            BuildControls();
            BuildConstraintsPanel();
            BuildEmptyGrid();

            if (string.IsNullOrWhiteSpace(scheduleJson))
            {
                currentReport = null;
                currentScheduleIndex = 0;
                ClearSlots();
                UpdatePaginationUI();
                SetSubtitle("Sin horario generado todavía.");
                return;
            }

            ScheduleReportPayload report = JsonUtility.FromJson<ScheduleReportPayload>(scheduleJson);
            if (report == null || report.schedules == null || report.schedules.Length == 0 || report.schedules[0] == null)
            {
                currentReport = null;
                currentScheduleIndex = 0;
                ClearSlots();
                UpdatePaginationUI();
                SetSubtitle("No se encontró el top 1 del horario.");
                return;
            }

            currentReport = report;
            currentScheduleIndex = Mathf.Clamp(currentScheduleIndex, 0, GetVisibleScheduleCount() - 1);
            RefreshSelectedSchedule();
            UpdatePaginationUI();
        }

        public void RenderFromSchedulePayload(BackendScheduleReportPayload reportPayload)
        {
            EnsureCanvas();
            BuildControls();
            BuildConstraintsPanel();
            BuildEmptyGrid();

            if (reportPayload == null || reportPayload.schedules == null || reportPayload.schedules.Length == 0)
            {
                currentReport = null;
                currentScheduleIndex = 0;
                ClearSlots();
                UpdatePaginationUI();
                SetSubtitle("No se encontró el top 1 del horario.");
                return;
            }

            currentReport = new ScheduleReportPayload
            {
                text = reportPayload.text,
                warnings = reportPayload.warnings,
                schedules = reportPayload.schedules
                    .Where(item => item != null)
                    .Select(ConvertScheduleEntry)
                    .ToArray(),
            };

            if (currentReport.schedules == null || currentReport.schedules.Length == 0)
            {
                currentReport = null;
                currentScheduleIndex = 0;
                ClearSlots();
                UpdatePaginationUI();
                SetSubtitle("No se encontró el top 1 del horario.");
                return;
            }

            currentScheduleIndex = Mathf.Clamp(currentScheduleIndex, 0, GetVisibleScheduleCount() - 1);
            RefreshSelectedSchedule();
            UpdatePaginationUI();
        }

        public void ToggleGridVisibility()
        {
            SetGridVisible(!gridVisible);
        }

        public void ShowNextSchedule()
        {
            if (!HasSchedules())
            {
                return;
            }

            currentScheduleIndex = WrapIndex(currentScheduleIndex + 1, GetVisibleScheduleCount());
            RefreshSelectedSchedule();
            UpdatePaginationUI();
        }

        public void ShowPreviousSchedule()
        {
            if (!HasSchedules())
            {
                return;
            }

            currentScheduleIndex = WrapIndex(currentScheduleIndex - 1, GetVisibleScheduleCount());
            RefreshSelectedSchedule();
            UpdatePaginationUI();
        }

        public void ToggleConstraintsVisibility()
        {
            SetConstraintsVisible(!constraintsVisible);
        }

        public void ToggleCoursesVisibility()
        {
            SetCoursesVisible(!coursesVisible);
        }

        public void RenderFromStateJson(string stateJson)
        {
            EnsureCanvas();
            BuildControls();
            BuildConstraintsPanel();
            BuildCoursesPanel();

            currentState = null;

            if (string.IsNullOrWhiteSpace(stateJson))
            {
                UpdateConstraintsText("Sin restricciones cargadas.", false);
                return;
            }

            AgentStatePayload parsedState = JsonUtility.FromJson<AgentStatePayload>(stateJson);
            currentState = parsedState;

            string naturalLanguage = BuildConstraintsSummary(parsedState);
            bool hasStructuredData = parsedState != null && parsedState.draft != null && parsedState.draft.constraints != null;
            UpdateConstraintsText(naturalLanguage, hasStructuredData);

            string coursesSummary = BuildCoursesSummary(parsedState);
            bool hasCourses = parsedState != null && parsedState.draft != null && parsedState.draft.courses != null && parsedState.draft.courses.Length > 0;
            UpdateCoursesText(coursesSummary, hasCourses);
        }

        public void RenderFromStatePayload(BackendStatePayload statePayload)
        {
            EnsureCanvas();
            BuildControls();
            BuildConstraintsPanel();
            BuildCoursesPanel();

            if (statePayload == null)
            {
                currentState = null;
                UpdateConstraintsText("Sin restricciones cargadas.", false);
                UpdateCoursesText("Sin cursos cargados.", false);
                return;
            }

            AgentStatePayload parsedState = ConvertStatePayload(statePayload);
            currentState = parsedState;

            string naturalLanguage = BuildConstraintsSummary(parsedState);
            bool hasStructuredData = parsedState != null && parsedState.draft != null && parsedState.draft.constraints != null;
            UpdateConstraintsText(naturalLanguage, hasStructuredData);

            string coursesSummary = BuildCoursesSummary(parsedState);
            bool hasCourses = parsedState != null && parsedState.draft != null && parsedState.draft.courses != null && parsedState.draft.courses.Length > 0;
            UpdateCoursesText(coursesSummary, hasCourses);
        }

        private AgentStatePayload ConvertStatePayload(BackendStatePayload statePayload)
        {
            return new AgentStatePayload
            {
                draft = new AgentDraftPayload
                {
                    courses = statePayload.draft?.courses == null
                        ? Array.Empty<AgentCoursePayload>()
                        : statePayload.draft.courses
                            .Where(item => item != null)
                            .Select(course => new AgentCoursePayload
                            {
                                course = course.course,
                                group = course.group,
                                professor = course.professor,
                                meetings = course.meetings == null
                                    ? Array.Empty<AgentCourseMeetingPayload>()
                                    : course.meetings
                                        .Where(meeting => meeting != null)
                                        .Select(meeting => new AgentCourseMeetingPayload
                                        {
                                            day = meeting.day,
                                            start = meeting.start,
                                            end = meeting.end,
                                        })
                                        .ToArray(),
                            })
                            .ToArray(),
                    constraints = ConvertConstraintsPayload(statePayload.draft?.constraints),
                },
            };
        }

        private AgentConstraintsPayload ConvertConstraintsPayload(BackendConstraintsPayload constraints)
        {
            if (constraints == null)
            {
                return null;
            }

            return new AgentConstraintsPayload
            {
                hard = ConvertRules(constraints.hard),
                soft = ConvertRules(constraints.soft),
                optimization = new AgentOptimizationPayload
                {
                    objectives = constraints.optimization?.objectives == null
                        ? Array.Empty<AgentObjectivePayload>()
                        : constraints.optimization.objectives
                            .Where(item => item != null)
                            .Select(item => new AgentObjectivePayload
                            {
                                @operator = item.@operator,
                                target = item.target,
                                weight = item.weight,
                                priority = item.priority,
                                aggregation = item.aggregation,
                            })
                            .ToArray(),
                },
                scoring = constraints.scoring == null
                    ? null
                    : new AgentScoringPayload
                    {
                        mode = constraints.scoring.mode,
                        per = constraints.scoring.per,
                    },
            };
        }

        private AgentConstraintRule[] ConvertRules(BackendRulePayload[] rules)
        {
            if (rules == null)
            {
                return Array.Empty<AgentConstraintRule>();
            }

            return rules
                .Where(item => item != null)
                .Select(item => new AgentConstraintRule
                {
                    type = item.type,
                    scope = item.scope,
                    @operator = item.@operator,
                    reason = item.reason,
                    target = item.target,
                    category = item.category,
                    preference_level = item.preference_level,
                    value = item.value,
                    days = item.days,
                    range = item.range == null
                        ? null
                        : new AgentTimeRange
                        {
                            start = item.range.start,
                            end = item.range.end,
                        },
                    values = item.values,
                })
                .ToArray();
        }

        private ScheduleEntry ConvertScheduleEntry(BackendSchedulePayload payload)
        {
            return new ScheduleEntry
            {
                meta = payload.meta == null
                    ? null
                    : new ScheduleMeta
                    {
                        raw_score = payload.meta.raw_score,
                        distinct_courses = payload.meta.distinct_courses,
                        distinct_days = payload.meta.distinct_days,
                    },
                blocks = payload.blocks == null
                    ? Array.Empty<ScheduleBlock>()
                    : payload.blocks
                        .Where(item => item != null)
                        .Select(item => new ScheduleBlock
                        {
                            day = item.day,
                            start = item.start,
                            end = item.end,
                            course = item.course,
                            group = item.group,
                            professor = item.professor,
                            tags = item.tags,
                        })
                        .ToArray(),
            };
        }

        private void EnsureCanvas()
        {
            if (rootPanel != null)
            {
                return;
            }

            Canvas canvas = targetCanvas;
            if (canvas == null && createCanvasIfMissing)
            {
                GameObject canvasObject = new GameObject("ScheduleGridCanvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
                canvas = canvasObject.GetComponent<Canvas>();
                canvas.renderMode = RenderMode.ScreenSpaceOverlay;

                CanvasScaler scaler = canvasObject.GetComponent<CanvasScaler>();
                scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
                scaler.referenceResolution = new Vector2(1920f, 1080f);
                scaler.matchWidthOrHeight = 0.5f;
            }

            if (canvas == null)
            {
                Debug.LogWarning("[ScheduleGridCanvas] No hay Canvas asignado y createCanvasIfMissing está desactivado.");
                return;
            }

            targetCanvas = canvas;

            GameObject panelObject = new GameObject("ScheduleBoard", typeof(RectTransform), typeof(Image));
            panelObject.transform.SetParent(targetCanvas.transform, false);

            rootPanel = panelObject.GetComponent<RectTransform>();
            rootPanel.anchorMin = new Vector2(0.5f, 0.5f);
            rootPanel.anchorMax = new Vector2(0.5f, 0.5f);
            rootPanel.pivot = new Vector2(0.5f, 0.5f);
            rootPanel.sizeDelta = canvasSize;
            rootPanel.anchoredPosition = Vector2.zero;

            Image panelImage = panelObject.GetComponent<Image>();
            panelImage.color = boardBackground;

            if (panelObject.GetComponent<CanvasGroup>() == null)
            {
                panelObject.AddComponent<CanvasGroup>();
            }

            VerticalLayoutGroup panelLayout = panelObject.AddComponent<VerticalLayoutGroup>();
            panelLayout.padding = new RectOffset(
                Mathf.RoundToInt(contentPadding.x),
                Mathf.RoundToInt(contentPadding.z),
                Mathf.RoundToInt(contentPadding.y),
                Mathf.RoundToInt(contentPadding.w));
            panelLayout.spacing = 0f;
            panelLayout.childAlignment = TextAnchor.UpperCenter;
            panelLayout.childControlHeight = true;
            panelLayout.childControlWidth = true;
            panelLayout.childForceExpandHeight = false;
            panelLayout.childForceExpandWidth = true;

            ContentSizeFitter panelFitter = panelObject.AddComponent<ContentSizeFitter>();
            panelFitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            panelFitter.verticalFit = ContentSizeFitter.FitMode.Unconstrained;

            GameObject contentObject = new GameObject("Content", typeof(RectTransform));
            contentObject.transform.SetParent(rootPanel, false);
            RectTransform contentRect = contentObject.GetComponent<RectTransform>();
            contentRect.anchorMin = Vector2.zero;
            contentRect.anchorMax = Vector2.one;
            contentRect.offsetMin = Vector2.zero;
            contentRect.offsetMax = Vector2.zero;

            VerticalLayoutGroup contentLayout = contentObject.AddComponent<VerticalLayoutGroup>();
            contentLayout.padding = new RectOffset(0, 0, 0, 0);
            contentLayout.spacing = 0f;
            contentLayout.childAlignment = TextAnchor.UpperCenter;
            contentLayout.childControlHeight = true;
            contentLayout.childControlWidth = true;
            contentLayout.childForceExpandHeight = false;
            contentLayout.childForceExpandWidth = true;

            ContentSizeFitter contentFitter = contentObject.AddComponent<ContentSizeFitter>();
            contentFitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            contentFitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            titleText = CreateTextElement("Title", "Horario top 1", 34, FontStyles.Bold, TextAlignmentOptions.Center);
            titleText.transform.SetParent(contentObject.transform, false);
            AddLayout(titleText.rectTransform, titleHeight);

            subtitleText = CreateTextElement("Subtitle", "Grilla vacía esperando horario...", 18, FontStyles.Normal, TextAlignmentOptions.Center);
            subtitleText.transform.SetParent(contentObject.transform, false);
            AddLayout(subtitleText.rectTransform, subtitleHeight);

            GameObject gridContainerObject = new GameObject("GridContainer", typeof(RectTransform));
            gridContainerObject.transform.SetParent(contentObject.transform, false);
            RectTransform gridContainerRect = gridContainerObject.GetComponent<RectTransform>();
            gridContainerRect.anchorMin = new Vector2(0f, 0f);
            gridContainerRect.anchorMax = new Vector2(1f, 1f);
            gridContainerRect.offsetMin = new Vector2(0f, 0f);
            gridContainerRect.offsetMax = new Vector2(0f, 0f);
            gridContainerRect.pivot = new Vector2(0.5f, 0.5f);

            HorizontalLayoutGroup gridContainerLayout = gridContainerObject.AddComponent<HorizontalLayoutGroup>();
            gridContainerLayout.padding = new RectOffset(Mathf.RoundToInt(gridHorizontalPadding), Mathf.RoundToInt(gridHorizontalPadding), 0, 0);
            gridContainerLayout.childAlignment = TextAnchor.UpperCenter;
            gridContainerLayout.childControlHeight = true;
            gridContainerLayout.childControlWidth = true;
            gridContainerLayout.childForceExpandHeight = false;
            gridContainerLayout.childForceExpandWidth = true;
            gridContainerLayout.spacing = 0f;

            LayoutElement gridContainerElement = gridContainerObject.AddComponent<LayoutElement>();
            gridContainerElement.flexibleWidth = 1f;
            gridContainerElement.flexibleHeight = 1f;

            GameObject gridObject = new GameObject("Grid", typeof(RectTransform));
            gridObject.transform.SetParent(gridContainerObject.transform, false);
            gridRoot = gridObject.GetComponent<RectTransform>();
            gridRoot.anchorMin = new Vector2(0f, 0f);
            gridRoot.anchorMax = new Vector2(1f, 1f);
            gridRoot.offsetMin = new Vector2(0f, 0f);
            gridRoot.offsetMax = new Vector2(0f, 0f);
            gridRoot.pivot = new Vector2(0.5f, 0.5f);

            VerticalLayoutGroup gridLayout = gridObject.AddComponent<VerticalLayoutGroup>();
            gridLayout.padding = new RectOffset(0, 0, Mathf.RoundToInt(gridTopSpacing.y), 0);
            gridLayout.spacing = rowSpacing;
            gridLayout.childAlignment = TextAnchor.UpperCenter;
            gridLayout.childControlHeight = true;
            gridLayout.childControlWidth = true;
            gridLayout.childForceExpandHeight = false;
            gridLayout.childForceExpandWidth = true;

            ContentSizeFitter gridFitter = gridObject.AddComponent<ContentSizeFitter>();
            gridFitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            gridFitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            BuildScheduleNavigation(contentObject.transform);
        }

        private void BuildControls()
        {
            if (controlsLeftPanel != null || controlsRightPanel != null)
            {
                return;
            }

            if (targetCanvas == null)
            {
                return;
            }

            GameObject controlsLeftObject = new GameObject("ScheduleControlsLeft", typeof(RectTransform));
            controlsLeftObject.transform.SetParent(targetCanvas.transform, false);
            controlsLeftPanel = controlsLeftObject.GetComponent<RectTransform>();
            controlsLeftPanel.anchorMin = new Vector2(0f, 1f);
            controlsLeftPanel.anchorMax = new Vector2(0f, 1f);
            controlsLeftPanel.pivot = new Vector2(0f, 1f);
            controlsLeftPanel.anchoredPosition = new Vector2(controlsOffset.x, -controlsOffset.y);

            HorizontalLayoutGroup leftLayout = controlsLeftObject.AddComponent<HorizontalLayoutGroup>();
            leftLayout.spacing = controlButtonSpacing;
            leftLayout.childAlignment = TextAnchor.MiddleLeft;
            leftLayout.childControlHeight = true;
            leftLayout.childControlWidth = true;
            leftLayout.childForceExpandHeight = false;
            leftLayout.childForceExpandWidth = false;

            ContentSizeFitter leftFitter = controlsLeftObject.AddComponent<ContentSizeFitter>();
            leftFitter.horizontalFit = ContentSizeFitter.FitMode.PreferredSize;
            leftFitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            constraintsButton = CreateControlButton(controlsLeftObject.transform, "ToggleConstraintsButton", "Restricciones", 160f);
            constraintsButton.onClick.AddListener(ToggleConstraintsVisibility);
            constraintsButtonLabel = constraintsButton.GetComponentInChildren<TMP_Text>(true);

            coursesButton = CreateControlButton(controlsLeftObject.transform, "ToggleCoursesButton", "Cursos", 130f);
            coursesButton.onClick.AddListener(ToggleCoursesVisibility);
            coursesButtonLabel = coursesButton.GetComponentInChildren<TMP_Text>(true);

            GameObject controlsRightObject = new GameObject("ScheduleControlsRight", typeof(RectTransform));
            controlsRightObject.transform.SetParent(targetCanvas.transform, false);
            controlsRightPanel = controlsRightObject.GetComponent<RectTransform>();
            controlsRightPanel.anchorMin = new Vector2(1f, 1f);
            controlsRightPanel.anchorMax = new Vector2(1f, 1f);
            controlsRightPanel.pivot = new Vector2(1f, 1f);
            controlsRightPanel.anchoredPosition = new Vector2(-controlsOffset.x, -controlsOffset.y);

            HorizontalLayoutGroup rightLayout = controlsRightObject.AddComponent<HorizontalLayoutGroup>();
            rightLayout.spacing = controlButtonSpacing;
            rightLayout.childAlignment = TextAnchor.MiddleRight;
            rightLayout.childControlHeight = true;
            rightLayout.childControlWidth = true;
            rightLayout.childForceExpandHeight = false;
            rightLayout.childForceExpandWidth = false;

            ContentSizeFitter rightFitter = controlsRightObject.AddComponent<ContentSizeFitter>();
            rightFitter.horizontalFit = ContentSizeFitter.FitMode.PreferredSize;
            rightFitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            toggleButton = CreateControlButton(controlsRightObject.transform, "ToggleGridButton", "Mostrar horario", controlButtonWidth);
            toggleButton.onClick.AddListener(ToggleGridVisibility);
            toggleButtonLabel = toggleButton.GetComponentInChildren<TMP_Text>(true);

            UpdatePaginationUI();
        }

        private void BuildScheduleNavigation(Transform parent)
        {
            if (scheduleNavPanel != null || parent == null)
            {
                return;
            }

            GameObject navObject = new GameObject("ScheduleNav", typeof(RectTransform));
            navObject.transform.SetParent(parent, false);
            navObject.transform.SetSiblingIndex(0);
            scheduleNavPanel = navObject.GetComponent<RectTransform>();

            HorizontalLayoutGroup navLayout = navObject.AddComponent<HorizontalLayoutGroup>();
            navLayout.spacing = controlButtonSpacing;
            navLayout.childAlignment = TextAnchor.MiddleCenter;
            navLayout.childControlHeight = true;
            navLayout.childControlWidth = true;
            navLayout.childForceExpandHeight = false;
            navLayout.childForceExpandWidth = false;

            ContentSizeFitter navFitter = navObject.AddComponent<ContentSizeFitter>();
            navFitter.horizontalFit = ContentSizeFitter.FitMode.PreferredSize;
            navFitter.verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            previousButton = CreateControlButton(navObject.transform, "PreviousScheduleButton", "Anterior", 130f);
            previousButton.onClick.AddListener(ShowPreviousSchedule);
            previousButtonLabel = previousButton.GetComponentInChildren<TMP_Text>(true);

            if (titleText != null)
            {
                titleText.transform.SetParent(navObject.transform, false);
                LayoutElement titleLayout = titleText.GetComponent<LayoutElement>();
                if (titleLayout == null)
                {
                    titleLayout = titleText.gameObject.AddComponent<LayoutElement>();
                }
                titleLayout.preferredHeight = titleHeight;
                titleLayout.minHeight = titleHeight;
                titleLayout.flexibleWidth = 1f;
            }

            pageLabel = CreateLabel(navObject.transform, "PageLabel", "1/1", 26, FontStyles.Bold, new Color(1f, 1f, 1f, 0.9f));
            AddLayout(pageLabel.rectTransform, controlButtonHeight);

            nextButton = CreateControlButton(navObject.transform, "NextScheduleButton", "Siguiente", 130f);
            nextButton.onClick.AddListener(ShowNextSchedule);
            nextButtonLabel = nextButton.GetComponentInChildren<TMP_Text>(true);

            UpdateNavigationVisibility();
        }

        private void BuildConstraintsPanel()
        {
            if (constraintsPanel != null)
            {
                return;
            }

            if (targetCanvas == null)
            {
                return;
            }

            GameObject panelObject = new GameObject("ConstraintsPanel", typeof(RectTransform), typeof(Image));
            panelObject.transform.SetParent(targetCanvas.transform, false);

            constraintsPanel = panelObject.GetComponent<RectTransform>();
            constraintsPanel.anchorMin = new Vector2(0f, 1f);
            constraintsPanel.anchorMax = new Vector2(0f, 1f);
            constraintsPanel.pivot = new Vector2(0f, 1f);
            constraintsPanel.anchoredPosition = new Vector2(constraintsPanelOffset.x, -constraintsPanelOffset.y);
            constraintsPanel.sizeDelta = new Vector2(constraintsPanelWidth, constraintsPanelHeight);

            Image panelImage = panelObject.GetComponent<Image>();
            panelImage.color = new Color(0.09f, 0.10f, 0.13f, 0.96f);

            VerticalLayoutGroup layout = panelObject.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(16, 16, 16, 16);
            layout.spacing = 8f;
            layout.childAlignment = TextAnchor.UpperLeft;
            layout.childControlHeight = true;
            layout.childControlWidth = true;
            layout.childForceExpandHeight = false;
            layout.childForceExpandWidth = true;

            ContentSizeFitter fitter = panelObject.AddComponent<ContentSizeFitter>();
            fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            fitter.verticalFit = ContentSizeFitter.FitMode.Unconstrained;

            TMP_Text title = CreateLabel(panelObject.transform, "ConstraintsTitle", "Restricciones activas", 24, FontStyles.Bold, Color.white);
            AddLayout(title.rectTransform, 30f);

            constraintsText = CreateLabel(panelObject.transform, "ConstraintsText", "Sin restricciones cargadas.", 18, FontStyles.Normal, new Color(0.92f, 0.94f, 0.97f, 0.95f));
            constraintsText.alignment = TextAlignmentOptions.TopLeft;
            constraintsText.textWrappingMode = TextWrappingModes.Normal;
            constraintsText.fontSizeMin = 14;
            constraintsText.fontSizeMax = 18;
            AddLayout(constraintsText.rectTransform, Mathf.Max(120f, constraintsPanel.sizeDelta.y - 60f));
        }

        private void BuildCoursesPanel()
        {
            if (coursesPanel != null)
            {
                return;
            }

            if (targetCanvas == null)
            {
                return;
            }

            GameObject panelObject = new GameObject("CoursesPanel", typeof(RectTransform), typeof(Image));
            panelObject.transform.SetParent(targetCanvas.transform, false);

            coursesPanel = panelObject.GetComponent<RectTransform>();
            coursesPanel.anchorMin = new Vector2(0f, 1f);
            coursesPanel.anchorMax = new Vector2(0f, 1f);
            coursesPanel.pivot = new Vector2(0f, 1f);
            coursesPanel.anchoredPosition = new Vector2(coursesPanelOffset.x, -coursesPanelOffset.y);
            coursesPanel.sizeDelta = new Vector2(coursesPanelWidth, coursesPanelHeight);

            Image panelImage = panelObject.GetComponent<Image>();
            panelImage.color = new Color(0.09f, 0.10f, 0.13f, 0.96f);

            VerticalLayoutGroup layout = panelObject.AddComponent<VerticalLayoutGroup>();
            layout.padding = new RectOffset(16, 16, 16, 16);
            layout.spacing = 8f;
            layout.childAlignment = TextAnchor.UpperLeft;
            layout.childControlHeight = true;
            layout.childControlWidth = true;
            layout.childForceExpandHeight = false;
            layout.childForceExpandWidth = true;

            ContentSizeFitter fitter = panelObject.AddComponent<ContentSizeFitter>();
            fitter.horizontalFit = ContentSizeFitter.FitMode.Unconstrained;
            fitter.verticalFit = ContentSizeFitter.FitMode.Unconstrained;

            TMP_Text title = CreateLabel(panelObject.transform, "CoursesTitle", "Cursos en consideración", 24, FontStyles.Bold, Color.white);
            AddLayout(title.rectTransform, 30f);

            coursesText = CreateLabel(panelObject.transform, "CoursesText", "Sin cursos cargados.", 18, FontStyles.Normal, new Color(0.92f, 0.94f, 0.97f, 0.95f));
            coursesText.alignment = TextAlignmentOptions.TopLeft;
            coursesText.textWrappingMode = TextWrappingModes.Normal;
            coursesText.fontSizeMin = 14;
            coursesText.fontSizeMax = 18;
            AddLayout(coursesText.rectTransform, Mathf.Max(120f, coursesPanel.sizeDelta.y - 60f));
        }

        private Button CreateControlButton(Transform parent, string objectName, string text, float width)
        {
            GameObject buttonObject = new GameObject(objectName, typeof(RectTransform), typeof(Image), typeof(Button), typeof(LayoutElement));
            buttonObject.transform.SetParent(parent, false);

            Image image = buttonObject.GetComponent<Image>();
            image.color = headerBackground;

            Button button = buttonObject.GetComponent<Button>();
            ColorBlock colors = button.colors;
            colors.normalColor = headerBackground;
            colors.highlightedColor = new Color(headerBackground.r + 0.08f, headerBackground.g + 0.08f, headerBackground.b + 0.08f, 1f);
            colors.pressedColor = new Color(hourBackground.r, hourBackground.g, hourBackground.b, 1f);
            colors.selectedColor = colors.highlightedColor;
            colors.disabledColor = new Color(0.25f, 0.25f, 0.25f, 0.7f);
            button.colors = colors;

            LayoutElement layout = buttonObject.GetComponent<LayoutElement>();
            layout.preferredWidth = width;
            layout.minWidth = width;
            layout.preferredHeight = controlButtonHeight;
            layout.minHeight = controlButtonHeight;

            TMP_Text label = CreateLabel(buttonObject.transform, objectName + "Label", text, 20, FontStyles.Bold, Color.white);
            label.rectTransform.anchorMin = Vector2.zero;
            label.rectTransform.anchorMax = Vector2.one;
            label.rectTransform.offsetMin = Vector2.zero;
            label.rectTransform.offsetMax = Vector2.zero;

            return button;
        }

        private TMP_Text CreateLabel(Transform parent, string name, string content, int fontSize, FontStyles style, Color color)
        {
            GameObject textObject = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI));
            textObject.transform.SetParent(parent, false);

            RectTransform rectTransform = textObject.GetComponent<RectTransform>();
            rectTransform.anchorMin = Vector2.zero;
            rectTransform.anchorMax = Vector2.one;
            rectTransform.offsetMin = new Vector2(8f, 6f);
            rectTransform.offsetMax = new Vector2(-8f, -6f);

            TMP_Text textComponent = textObject.GetComponent<TextMeshProUGUI>();
            textComponent.text = content;
            textComponent.fontSize = fontSize;
            textComponent.fontStyle = style;
            textComponent.alignment = TextAlignmentOptions.Center;
            textComponent.color = color;
            textComponent.enableAutoSizing = true;
            textComponent.fontSizeMin = Mathf.Max(12, fontSize - 6);
            textComponent.fontSizeMax = fontSize;
            return textComponent;
        }

        private void SetGridVisible(bool visible)
        {
            gridVisible = visible;

            if (rootPanel != null)
            {
                rootPanel.gameObject.SetActive(visible);
            }

            if (toggleButtonLabel != null)
            {
                toggleButtonLabel.text = visible ? "Ocultar horario" : "Mostrar horario";
            }

            bool hasSchedules = HasSchedules();
            if (previousButton != null)
            {
                previousButton.interactable = visible && hasSchedules;
            }

            if (nextButton != null)
            {
                nextButton.interactable = visible && hasSchedules;
            }

            if (visible)
            {
                RefreshSelectedSchedule();
            }

            UpdateNavigationVisibility();
        }

        private void SetConstraintsVisible(bool visible)
        {
            constraintsVisible = visible;

            if (constraintsPanel != null)
            {
                constraintsPanel.gameObject.SetActive(visible);
            }

            if (constraintsButtonLabel != null)
            {
                constraintsButtonLabel.text = visible ? "Ocultar restricciones" : "Restricciones";
            }

            if (visible && constraintsText != null && string.IsNullOrWhiteSpace(constraintsText.text))
            {
                constraintsText.text = "Sin restricciones cargadas.";
            }
        }

        private void UpdateConstraintsText(string text, bool hasStructuredData)
        {
            if (constraintsText == null)
            {
                return;
            }

            constraintsText.text = string.IsNullOrWhiteSpace(text)
                ? "Sin restricciones cargadas."
                : text;

            if (constraintsButton != null)
            {
                constraintsButton.interactable = hasStructuredData || !string.IsNullOrWhiteSpace(text);
            }

            if (constraintsVisible && constraintsPanel != null)
            {
                constraintsPanel.gameObject.SetActive(true);
            }
        }

        private void SetCoursesVisible(bool visible)
        {
            coursesVisible = visible;

            if (coursesPanel != null)
            {
                coursesPanel.gameObject.SetActive(visible);
            }

            if (coursesButtonLabel != null)
            {
                coursesButtonLabel.text = visible ? "Ocultar cursos" : "Cursos";
            }

            if (visible && coursesText != null && string.IsNullOrWhiteSpace(coursesText.text))
            {
                coursesText.text = "Sin cursos cargados.";
            }
        }

        private void UpdateCoursesText(string text, bool hasStructuredData)
        {
            if (coursesText == null)
            {
                return;
            }

            coursesText.text = string.IsNullOrWhiteSpace(text)
                ? "Sin cursos cargados."
                : text;

            if (coursesButton != null)
            {
                coursesButton.interactable = hasStructuredData || !string.IsNullOrWhiteSpace(text);
            }

            if (coursesVisible && coursesPanel != null)
            {
                coursesPanel.gameObject.SetActive(true);
            }
        }

        private string BuildCoursesSummary(AgentStatePayload state)
        {
            if (state == null || state.draft == null)
            {
                return "Sin cursos cargados.";
            }

            AgentCoursePayload[] courses = state.draft.courses ?? Array.Empty<AgentCoursePayload>();
            if (courses.Length == 0)
            {
                return "Sin cursos cargados.";
            }

            var grouped = new Dictionary<string, List<AgentCoursePayload>>(StringComparer.OrdinalIgnoreCase);
            var order = new List<string>();

            foreach (AgentCoursePayload course in courses)
            {
                string courseName = string.IsNullOrWhiteSpace(course?.course) ? "Curso sin nombre" : course.course.Trim();
                if (!grouped.ContainsKey(courseName))
                {
                    grouped[courseName] = new List<AgentCoursePayload>();
                    order.Add(courseName);
                }

                grouped[courseName].Add(course);
            }

            var lines = new List<string>();
            foreach (string courseName in order)
            {
                if (lines.Count > 0)
                {
                    lines.Add(string.Empty);
                }

                lines.Add($"{courseName}:");

                foreach (AgentCoursePayload course in grouped[courseName])
                {
                    string line = FormatCourseLine(course);
                    if (!string.IsNullOrWhiteSpace(line))
                    {
                        lines.Add($"- {line}");
                    }
                }
            }

            return lines.Count == 0 ? "Sin cursos cargados." : string.Join("\n", lines);
        }

        private string FormatCourseLine(AgentCoursePayload course)
        {
            if (course == null)
            {
                return string.Empty;
            }

            string group = string.IsNullOrWhiteSpace(course.group) ? "Sin grupo" : course.group.Trim();
            string professor = string.IsNullOrWhiteSpace(course.professor) ? "Desconocido" : course.professor.Trim();

            List<AgentCourseMeetingPayload> meetings = course.meetings == null
                ? new List<AgentCourseMeetingPayload>()
                : course.meetings.Where(meeting => meeting != null).ToList();

            if (meetings.Count == 0)
            {
                return $"{group} - {professor} - sin horario";
            }

            List<string> meetingParts = new List<string>();

            foreach (AgentCourseMeetingPayload meeting in meetings)
            {
                if (meeting == null)
                {
                    continue;
                }

                string dayLabel = NormalizeDay(meeting.day);
                string start = NormalizeTimeLong(meeting.start);
                string end = NormalizeTimeLong(meeting.end);
                if (string.IsNullOrWhiteSpace(dayLabel) || string.IsNullOrWhiteSpace(start) || string.IsNullOrWhiteSpace(end))
                {
                    continue;
                }

                meetingParts.Add($"{dayLabel} {start} a {end}");
            }

            string meetingsText = meetingParts.Count == 0 ? "sin horario" : string.Join(" - ", meetingParts);
            return $"{group} - {professor} - {meetingsText}";
        }

        private string NormalizeTimeLong(string timeValue)
        {
            if (string.IsNullOrWhiteSpace(timeValue))
            {
                return string.Empty;
            }

            string[] parts = timeValue.Split(':');
            if (parts.Length < 2)
            {
                return timeValue.Trim();
            }

            if (!int.TryParse(parts[0], out int hours) || !int.TryParse(parts[1], out int minutes))
            {
                return timeValue.Trim();
            }

            return $"{hours}:{minutes:00}";
        }

        private string BuildRawRuleText(AgentConstraintRule rule)
        {
            return "Regla no reconocida o incompleta.";
        }

        private string BuildConstraintsSummary(AgentStatePayload state)
        {
            AgentConstraintsPayload constraints = state?.draft?.constraints;
            if (constraints == null)
            {
                return "Sin restricciones cargadas.";
            }

            List<string> lines = new List<string>();
            List<string> hardLines = new List<string>();
            List<string> softLines = new List<string>();
            List<string> objectiveLines = new List<string>();

            if (constraints.hard != null && constraints.hard.Length > 0)
            {
                foreach (AgentConstraintRule rule in constraints.hard)
                {
                    string line = FormatConstraintRule(rule);
                    if (!string.IsNullOrWhiteSpace(line))
                    {
                        hardLines.Add(line);
                    }
                }
            }

            if (constraints.soft != null && constraints.soft.Length > 0)
            {
                foreach (AgentConstraintRule rule in constraints.soft)
                {
                    string line = FormatConstraintRule(rule);
                    if (!string.IsNullOrWhiteSpace(line))
                    {
                        softLines.Add(line);
                    }
                }
            }

            if (constraints.optimization != null && constraints.optimization.objectives != null && constraints.optimization.objectives.Length > 0)
            {
                foreach (AgentObjectivePayload objective in constraints.optimization.objectives)
                {
                    string line = FormatObjective(objective);
                    if (!string.IsNullOrWhiteSpace(line))
                    {
                        objectiveLines.Add(line);
                    }
                }
            }

            if (hardLines.Count > 0)
            {
                lines.Add("Restricciones duras:");
                lines.AddRange(hardLines.Select(item => $"- {item}"));
            }

            if (softLines.Count > 0)
            {
                if (lines.Count > 0)
                {
                    lines.Add(string.Empty);
                }

                lines.Add("Preferencias:");
                lines.AddRange(softLines.Select(item => $"- {item}"));
            }

            if (objectiveLines.Count > 0)
            {
                if (lines.Count > 0)
                {
                    lines.Add(string.Empty);
                }

                lines.Add("Objetivos de optimización:");
                lines.AddRange(objectiveLines.Select(item => $"- {item}"));
            }

            if (constraints.scoring != null)
            {
                if (lines.Count > 0)
                {
                    lines.Add(string.Empty);
                }

                lines.Add($"Puntaje: modo {constraints.scoring.mode ?? "fixed"}, por {constraints.scoring.per}");
            }

            if (lines.Count == 0)
            {
                return "Sin restricciones cargadas.";
            }

            return string.Join("\n", lines);
        }

        private string FormatConstraintRule(AgentConstraintRule rule)
        {
            if (rule == null)
            {
                return string.Empty;
            }

            string op = NormalizeOperator(rule.@operator);
            string type = (rule.type ?? string.Empty).Trim().ToLowerInvariant();

            if (type == "time_window" && rule.range != null)
            {
                string rangeText = $"{rule.range.start ?? "?"} a {rule.range.end ?? "?"}";
                if (op == "outside" || op == "avoid")
                {
                    return $"Evitar entre {rangeText}.";
                }

                if (op == "between" || op == "prefer")
                {
                    return $"Preferir entre {rangeText}.";
                }

                return $"{Capitalize(op)} entre {rangeText}.";
            }

            if (type == "max_courses_per_day")
            {
                return $"Máximo {rule.value} cursos por día.";
            }

            if (type == "max_per_category" || type == "tag")
            {
                string label = !string.IsNullOrWhiteSpace(rule.category)
                    ? rule.category
                    : (!string.IsNullOrWhiteSpace(rule.target) ? rule.target : FirstNonEmptyValue(rule.values, "categoría"));

                if (op == "avoid" || op == "exclude")
                {
                    return $"Evitar etiqueta {label}.";
                }

                if (op == "prefer" || op == "include")
                {
                    return $"Preferir etiqueta {label}.";
                }

                return rule.value > 0
                    ? $"Límite {rule.value} para etiqueta {label}."
                    : $"Regla de etiqueta {label}.";
            }

            if (type == "day" && rule.days != null && rule.days.Length > 0)
            {
                string daysText = string.Join(", ", rule.days.Where(item => !string.IsNullOrWhiteSpace(item)));
                if (op == "prefer")
                {
                    return $"Preferir {daysText}.";
                }

                if (op == "avoid" || op == "exclude")
                {
                    return $"Evitar {daysText}.";
                }

                return $"{Capitalize(op)} {daysText}.";
            }

            if (type == "professor" || type == "course" || type == "group" || type == "campus")
            {
                string entity = FirstNonEmptyValue(rule.values, rule.target);
                if (string.IsNullOrWhiteSpace(entity))
                {
                    return "Regla de entidad sin valores.";
                }

                if (op == "prefer")
                {
                    return $"Preferir {entity}.";
                }

                if (op == "avoid" || op == "exclude")
                {
                    return $"Evitar {entity}.";
                }

                if (op == "include")
                {
                    return $"Incluir {entity}.";
                }

                return $"{Capitalize(op)} {entity}.";
            }

            if (type == "metric" && !string.IsNullOrWhiteSpace(rule.target))
            {
                if (op == "<=" || op == ">=" || op == "==")
                {
                    return $"{rule.target} {op} {rule.value}.";
                }

                if (op == "prefer" || op == "include")
                {
                    return $"Preferir {rule.target} con valor {rule.value}.";
                }

                if (op == "avoid" || op == "exclude")
                {
                    return $"Evitar {rule.target} con valor {rule.value}.";
                }

                return $"{Capitalize(op)} {rule.target} con valor {rule.value}.";
            }

            return BuildRawRuleText(rule);
        }

        private string FirstNonEmptyValue(string[] values, string fallback = "")
        {
            if (values != null)
            {
                foreach (string value in values)
                {
                    if (!string.IsNullOrWhiteSpace(value))
                    {
                        return value.Trim();
                    }
                }
            }

            return string.IsNullOrWhiteSpace(fallback) ? string.Empty : fallback.Trim();
        }

        private string FormatObjective(AgentObjectivePayload objective)
        {
            if (objective == null)
            {
                return string.Empty;
            }

            string op = NormalizeOperator(objective.@operator);
            string target = string.IsNullOrWhiteSpace(objective.target) ? "objetivo" : objective.target.Trim();
            int priority = objective.priority > 0 ? objective.priority : 0;
            int weight = objective.weight > 0 ? objective.weight : 1;

            return $"{op} {target} (peso {weight}, prioridad {priority}).";
        }

        private string NormalizeOperator(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "" : value.Trim().ToLowerInvariant();
        }

        private string Capitalize(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
            {
                return string.Empty;
            }

            return char.ToUpperInvariant(value[0]) + value.Substring(1);
        }

        private void RefreshSelectedSchedule()
        {
            BuildEmptyGrid();
            ClearSlots();

            if (currentReport == null || currentReport.schedules == null || currentReport.schedules.Length == 0)
            {
                SetSubtitle("Sin horario generado todavía.");
                UpdatePaginationUI();
                return;
            }

            int count = GetVisibleScheduleCount();
            if (count <= 0)
            {
                SetSubtitle("Sin horario generado todavía.");
                UpdatePaginationUI();
                return;
            }

            currentScheduleIndex = WrapIndex(currentScheduleIndex, count);
            ScheduleEntry selectedSchedule = currentReport.schedules[currentScheduleIndex];
            ScheduleBlock[] blocks = selectedSchedule?.blocks ?? Array.Empty<ScheduleBlock>();
            ApplyBlocks(blocks);

            string reportTitle = string.IsNullOrWhiteSpace(currentReport.text)
                ? $"Horario {currentScheduleIndex + 1}/{count}"
                : $"{currentReport.text} - {currentScheduleIndex + 1}/{count}";
            SetSubtitle(reportTitle);
            UpdatePaginationUI();
        }

        private bool HasSchedules()
        {
            return GetVisibleScheduleCount() > 0;
        }

        private int GetVisibleScheduleCount()
        {
            if (currentReport == null || currentReport.schedules == null)
            {
                return 0;
            }

            return Mathf.Min(currentReport.schedules.Length, maxVisibleSchedules);
        }

        private int WrapIndex(int value, int count)
        {
            if (count <= 0)
            {
                return 0;
            }

            int result = value % count;
            if (result < 0)
            {
                result += count;
            }

            return result;
        }

        private void UpdatePaginationUI()
        {
            int count = Mathf.Max(GetVisibleScheduleCount(), 1);
            if (pageLabel != null)
            {
                pageLabel.text = HasSchedules() ? $"{currentScheduleIndex + 1}/{count}" : "0/0";
            }

            if (previousButton != null)
            {
                previousButton.interactable = HasSchedules();
            }

            if (nextButton != null)
            {
                nextButton.interactable = HasSchedules();
            }

            UpdateNavigationVisibility();
        }

        private void UpdateNavigationVisibility()
        {
            if (scheduleNavPanel == null)
            {
                return;
            }

            scheduleNavPanel.gameObject.SetActive(gridVisible);

            bool hasSchedules = HasSchedules();
            if (previousButton != null)
            {
                previousButton.interactable = gridVisible && hasSchedules;
            }

            if (nextButton != null)
            {
                nextButton.interactable = gridVisible && hasSchedules;
            }
        }

        private void BuildEmptyGrid()
        {
            if (gridBuilt && slotCells.Count > 0)
            {
                return;
            }

            if (gridRoot == null)
            {
                return;
            }

            ClearChildren(gridRoot);
            slotCells.Clear();

            GameObject headerRow = CreateRow("HeaderRow");
            headerRow.transform.SetParent(gridRoot, false);
            CreateHeaderCell(headerRow.transform, "Hora", hourColumnWidth, hourBackground);
            foreach (string day in OrderedDays)
            {
                CreateHeaderCell(headerRow.transform, day, dayColumnWidth, headerBackground);
            }

            for (int hour = startHour; hour < endHour; hour++)
            {
                GameObject rowObject = CreateRow($"Row_{hour:00}");
                rowObject.transform.SetParent(gridRoot, false);

                CreateHourCell(rowObject.transform, hour);

                foreach (string day in OrderedDays)
                {
                    CreateSlotCell(rowObject.transform, day, hour);
                }
            }

            gridBuilt = true;
        }

        private GameObject CreateRow(string name)
        {
            GameObject rowObject = new GameObject(name, typeof(RectTransform), typeof(HorizontalLayoutGroup));

            HorizontalLayoutGroup rowLayout = rowObject.GetComponent<HorizontalLayoutGroup>();
            rowLayout.spacing = cellSpacing;
            rowLayout.childControlWidth = true;
            rowLayout.childControlHeight = true;
            rowLayout.childForceExpandWidth = false;
            rowLayout.childForceExpandHeight = false;

            LayoutElement layout = rowObject.AddComponent<LayoutElement>();
            layout.preferredHeight = rowHeight;
            layout.minHeight = rowHeight;
            layout.flexibleHeight = 0f;
            layout.preferredWidth = dayColumnWidth * OrderedDays.Length + hourColumnWidth + cellSpacing * (OrderedDays.Length + 1);
            layout.flexibleWidth = 1f;

            return rowObject;
        }

        private void CreateHeaderCell(Transform parent, string label, float width, Color backgroundColor)
        {
            GameObject cellObject = CreateCellObject($"Header_{label}", backgroundColor, width);
            cellObject.transform.SetParent(parent, false);
            TMP_Text text = CreateTextElement("Label", label, 22, FontStyles.Bold, TextAlignmentOptions.Center);
            text.transform.SetParent(cellObject.transform, false);
            text.color = Color.white;
        }

        private void CreateHourCell(Transform parent, int hour)
        {
            GameObject cellObject = CreateCellObject($"Hour_{hour:00}", hourBackground, hourColumnWidth);
            cellObject.transform.SetParent(parent, false);
            TMP_Text text = CreateTextElement("Label", FormatHourLabel(hour), 20, FontStyles.Bold, TextAlignmentOptions.Center);
            text.transform.SetParent(cellObject.transform, false);
            text.color = Color.white;
        }

        private void CreateSlotCell(Transform parent, string day, int hour)
        {
            GameObject cellObject = CreateCellObject($"Slot_{day}_{hour:00}", emptySlotBackground, dayColumnWidth);
            cellObject.transform.SetParent(parent, false);

            TMP_Text text = CreateTextElement("Label", string.Empty, 18, FontStyles.Bold, TextAlignmentOptions.Center);
            text.transform.SetParent(cellObject.transform, false);
            text.color = emptySlotText;
            text.textWrappingMode = TextWrappingModes.Normal;

            if (!slotCells.ContainsKey(day))
            {
                slotCells[day] = new Dictionary<int, SlotCell>();
            }

            slotCells[day][hour] = new SlotCell
            {
                Background = cellObject.GetComponent<Image>(),
                Label = text,
            };
        }

        private GameObject CreateCellObject(string name, Color backgroundColor, float width)
        {
            GameObject cellObject = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(LayoutElement));

            Image image = cellObject.GetComponent<Image>();
            image.color = backgroundColor;

            LayoutElement layout = cellObject.GetComponent<LayoutElement>();
            layout.preferredWidth = width;
            layout.minWidth = width;
            layout.preferredHeight = rowHeight;
            layout.minHeight = rowHeight;
            layout.flexibleWidth = 0f;
            layout.flexibleHeight = 0f;

            return cellObject;
        }

        private TMP_Text CreateTextElement(string name, string content, int fontSize, FontStyles style, TextAlignmentOptions alignment)
        {
            GameObject textObject = new GameObject(name, typeof(RectTransform), typeof(TextMeshProUGUI));

            RectTransform rectTransform = textObject.GetComponent<RectTransform>();
            rectTransform.anchorMin = Vector2.zero;
            rectTransform.anchorMax = Vector2.one;
            rectTransform.offsetMin = new Vector2(8f, 6f);
            rectTransform.offsetMax = new Vector2(-8f, -6f);

            TMP_Text text = textObject.GetComponent<TextMeshProUGUI>();
            text.text = content;
            text.fontSize = fontSize;
            text.fontStyle = style;
            text.alignment = alignment;
            text.color = Color.white;
            text.enableAutoSizing = true;
            text.fontSizeMin = Mathf.Max(12, fontSize - 8);
            text.fontSizeMax = fontSize;

            return text;
        }

        private void ClearSlots()
        {
            foreach (var daySlots in slotCells.Values)
            {
                foreach (SlotCell cell in daySlots.Values)
                {
                    if (cell == null)
                    {
                        continue;
                    }

                    if (cell.Background != null)
                    {
                        cell.Background.color = emptySlotBackground;
                    }

                    if (cell.Label != null)
                    {
                        cell.Label.text = string.Empty;
                        cell.Label.color = emptySlotText;
                    }
                }
            }

            SetSubtitle("Grilla vacía esperando horario...");
        }

        private void ApplyBlocks(ScheduleBlock[] blocks)
        {
            foreach (ScheduleBlock block in blocks)
            {
                if (block == null)
                {
                    continue;
                }

                string day = NormalizeDay(block.day);
                if (string.IsNullOrWhiteSpace(day) || !slotCells.ContainsKey(day))
                {
                    continue;
                }

                int roundedStart = ClampHour(RoundToNearestHour(block.start));
                int roundedEnd = ClampHour(RoundToNearestHour(block.end));

                if (roundedEnd <= roundedStart)
                {
                    roundedEnd = Mathf.Min(endHour, roundedStart + 1);
                }

                roundedStart = Mathf.Clamp(roundedStart, startHour, endHour - 1);
                roundedEnd = Mathf.Clamp(roundedEnd, startHour + 1, endHour);

                for (int hour = roundedStart; hour < roundedEnd; hour++)
                {
                    if (!slotCells[day].TryGetValue(hour, out SlotCell cell) || cell == null)
                    {
                        continue;
                    }

                    string courseName = string.IsNullOrWhiteSpace(block.course) ? "Desconocido" : block.course.Trim();
                    if (cell.Label != null)
                    {
                        if (string.IsNullOrWhiteSpace(cell.Label.text))
                        {
                            cell.Label.text = courseName;
                        }
                        else if (!cell.Label.text.Split('\n').Contains(courseName))
                        {
                            cell.Label.text = cell.Label.text + "\n" + courseName;
                        }

                        cell.Label.color = filledSlotText;
                    }

                    if (cell.Background != null)
                    {
                        cell.Background.color = filledSlotBackground;
                    }
                }
            }
        }

        private void SetSubtitle(string message)
        {
            if (subtitleText != null)
            {
                subtitleText.text = message;
            }
        }

        private void ClearChildren(Transform parent)
        {
            for (int index = parent.childCount - 1; index >= 0; index--)
            {
                Transform child = parent.GetChild(index);
                if (child != null)
                {
                    Destroy(child.gameObject);
                }
            }
        }

        private void AddLayout(RectTransform rectTransform, float preferredHeight)
        {
            LayoutElement layout = rectTransform.gameObject.GetComponent<LayoutElement>();
            if (layout == null)
            {
                layout = rectTransform.gameObject.AddComponent<LayoutElement>();
            }

            layout.preferredHeight = preferredHeight;
            layout.minHeight = preferredHeight;
            layout.flexibleHeight = 0f;
        }

        private string NormalizeDay(string day)
        {
            if (string.IsNullOrWhiteSpace(day))
            {
                return string.Empty;
            }

            if (DayAliases.TryGetValue(day.Trim(), out string normalized))
            {
                return normalized;
            }

            return day.Trim();
        }

        private int RoundToNearestHour(string timeText)
        {
            if (string.IsNullOrWhiteSpace(timeText))
            {
                return startHour;
            }

            string[] parts = timeText.Split(':');
            if (parts.Length < 2 || !int.TryParse(parts[0], out int hour) || !int.TryParse(parts[1], out int minutes))
            {
                return startHour;
            }

            if (minutes >= 30)
            {
                hour += 1;
            }

            return hour;
        }

        private int ClampHour(int hour)
        {
            return Mathf.Clamp(hour, startHour, endHour);
        }

        private string FormatHourLabel(int hour)
        {
            return $"{hour:00}:00";
        }
    }
}

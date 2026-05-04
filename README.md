# Agente virtual corporizado para la planificación personalizada de horarios académicos

## Descripción general

Este repositorio contiene la propuesta inicial y la estructura base del proyecto desarrollado para el curso **PF-3311 Agentes Virtuales Inteligentes**, de la Maestría Profesional en Computación e Informática de la Universidad de Costa Rica.

El proyecto consiste en el diseño y evaluación de un **agente virtual corporizado** basado en un avatar robótico, cuyo propósito es apoyar a personas usuarias en la planificación personalizada de horarios académicos. El agente busca asistir durante la toma de decisiones, interpretando preferencias, señalando posibles conflictos y sugiriendo alternativas de horario.

A diferencia de una interfaz tradicional de planificación manual, el sistema propuesto incorpora interacción multimodal mediante representación visual, voz sintética, animaciones, blendshapes y lip-sync. El objetivo del estudio es comparar la experiencia de uso entre una interfaz tradicional y una interfaz asistida por un agente virtual corporizado.

## Título del proyecto

**Diseño y evaluación de un agente virtual corporizado basado en avatar robótico para apoyar la planificación personalizada de horarios académicos**

## Objetivo general

Evaluar si un agente virtual corporizado con interacción multimodal puede mejorar la planificación personalizada de horarios académicos en comparación con una interfaz tradicional manual.

## Objetivos específicos

- Diseñar un agente virtual corporizado con apariencia robótica para asistir la planificación de horarios.
- Implementar una interfaz interactiva en Unity para visualizar el agente y las opciones de horario.
- Integrar un modelo conversacional, como Gemini, para guiar la interacción con la persona usuaria.
- Incorporar servicios de voz, animaciones y lip-sync para apoyar la comunicación del agente.
- Comparar la interfaz tradicional y la interfaz con agente virtual en términos de desempeño, carga mental, usabilidad y experiencia de usuario.

## Preguntas de investigación

**RQ1.** ¿En qué medida el uso de un agente virtual corporizado con interacción multimodal influye en el desempeño del usuario durante la planificación de horarios académicos, en comparación con una interfaz tradicional manual?

**RQ2.** ¿Cómo afecta el uso del agente virtual corporizado la carga mental percibida y la usabilidad durante la planificación de horarios académicos?

**RQ3.** ¿Cómo perciben los usuarios la experiencia de interacción con un agente virtual corporizado en términos de claridad, acompañamiento, control y satisfacción durante la planificación de horarios?

## Arquitectura preliminar

El sistema se plantea como una arquitectura modular compuesta por:

- **Interfaz en Unity:** visualización del horario, avatar robótico e interacción principal.
- **Avatar corporizado:** representación visual del agente mediante animaciones, blendshapes y lip-sync.
- **Backend en Python:** lógica de planificación, validación de restricciones y comunicación con servicios externos.
- **Modelo conversacional Gemini:** interpretación de solicitudes, generación de respuestas y guía conversacional.
- **Servicios de voz:** generación de voz sintética mediante Text-to-Speech.
- **Módulo de evaluación:** registro de logs, tiempos de ejecución, interacciones y correcciones.

## Estructura del repositorio

```text
.
├── README.md
├── .gitignore
├── docs/
│   └── propuesta_agente_virtual_horarios.pdf
├── unity-app/
│   ├── Assets/
│   ├── Packages/
│   └── ProjectSettings/
├── backend/
│   ├── app.py
│   ├── gemini_service.py
│   ├── tts_service.py
│   ├── schedule_service.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
└── data/
    ├── courses_sample.json
    └── constraints_sample.json
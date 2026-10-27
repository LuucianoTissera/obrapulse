"""Taxonomía de causas de no cumplimiento (CNC, de Lean Construction / Last Planner)
y 'playbook' de análisis de causa raíz (5 Porqués) para cada una.

El playbook es el fallback determinista cuando no hay LLM disponible; es además el lugar
donde un ingeniero de procesos codifica conocimiento de obra.
"""

from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "CLIMA": "Clima / condiciones del terreno",
    "MATERIALES": "Falta o demora de materiales",
    "EQUIPOS": "Falla o falta de equipos / maquinaria",
    "MANO_OBRA": "Falta de mano de obra / ausentismo",
    "SUBCONTRATISTA": "Subcontratistas",
    "PROYECTO": "Proyecto / planos / definiciones",
    "INTERFERENCIAS": "Interferencias y permisos (servicios, terceros)",
    "SEGURIDAD": "Seguridad e higiene",
    "CALIDAD": "Calidad / retrabajo / ensayos",
    "OTROS": "Otros / no clasificado",
    "SIN_CAUSA": "Desvío sin causa registrada",
}

# Categorías que el ML / LLM pueden predecir (SIN_CAUSA se asigna por regla de datos)
CLASSIFIABLE: list[str] = [c for c in CATEGORIES if c != "SIN_CAUSA"]

PLAYBOOK: dict[str, dict[str, list[str]]] = {
    "CLIMA": {
        "porques": [
            "¿Por qué no se cumple la tarea? Las condiciones climáticas impiden trabajar.",
            "¿Por qué impacta tanto? La actividad está programada sin margen para clima adverso.",
            "¿Por qué sin margen? El cronograma no usa el pronóstico ni días de contingencia.",
            "¿Por qué no se usa el pronóstico? No hay una rutina semanal que lo incorpore al plan.",
            "Causa raíz probable: planificación semanal que no incorpora pronóstico ni tareas alternativas bajo techo o de bajo impacto.",
        ],
        "acciones": [
            "Incorporar el pronóstico a la reunión semanal de planificación.",
            "Definir un 'plan B' de tareas ejecutables con mal clima.",
            "Reprogramar tareas sensibles (hormigonado, asfalto) según ventanas climáticas.",
        ],
    },
    "MATERIALES": {
        "porques": [
            "¿Por qué se detiene la tarea? El material no está en obra en el momento requerido.",
            "¿Por qué no está? El pedido se hizo tarde o el proveedor entregó fuera de fecha.",
            "¿Por qué tarde? No se liberan los pedidos contra el cronograma de obra.",
            "¿Por qué no se vincula al cronograma? No hay un proceso de pedido con lead time por material.",
            "Causa raíz probable: abastecimiento sin lead times ni puntos de pedido ligados al plan de obra.",
        ],
        "acciones": [
            "Definir lead time por material crítico y emitir pedidos con anticipación.",
            "Revisar semanalmente el 'look-ahead' de materiales a 3 semanas.",
            "Evaluar proveedores alternativos y stock de seguridad para críticos (hormigón, asfalto, cable).",
        ],
    },
    "EQUIPOS": {
        "porques": [
            "¿Por qué se detiene la tarea? El equipo está averiado o no disponible.",
            "¿Por qué se averió? Mantenimiento correctivo en lugar de preventivo.",
            "¿Por qué correctivo? No hay plan de mantenimiento por horas de uso.",
            "¿Por qué no está disponible? La asignación de equipos entre obras no se coordina.",
            "Causa raíz probable: ausencia de plan de mantenimiento preventivo y de asignación centralizada de maquinaria.",
        ],
        "acciones": [
            "Plan de mantenimiento preventivo por horas de uso.",
            "Calendario centralizado de asignación de maquinaria entre obras.",
            "Definir equipo de reemplazo o alquiler para tareas críticas.",
        ],
    },
    "MANO_OBRA": {
        "porques": [
            "¿Por qué no se cumple? No hay suficiente gente en el frente de trabajo.",
            "¿Por qué falta gente? Ausentismo o reasignaciones entre obras.",
            "¿Por qué se reasigna sin aviso? No existe planificación de recursos a nivel de varias obras.",
            "¿Por qué no existe? La dotación se decide día a día.",
            "Causa raíz probable: ausencia de planificación de dotación por cuadrilla con visión multi-obra.",
        ],
        "acciones": [
            "Planificar dotación semanal por cuadrilla y obra.",
            "Analizar patrones de ausentismo (días previos a feriados, etc.).",
            "Capacitación cruzada para cubrir puestos críticos.",
        ],
    },
    "SUBCONTRATISTA": {
        "porques": [
            "¿Por qué se frena? El subcontratista no cumple su ventana de trabajo.",
            "¿Por qué no la cumple? Está atrasado en otra tarea o sin recursos.",
            "¿Por qué no se anticipa? No hay seguimiento semanal de compromisos con subcontratos.",
            "¿Por qué no hay seguimiento? Los compromisos no se formalizan en el plan semanal.",
            "Causa raíz probable: compromisos de subcontratistas no integrados al plan semanal con confirmación previa.",
        ],
        "acciones": [
            "Incluir a subcontratistas en la reunión semanal de planificación.",
            "Pedir confirmación de recursos 48 h antes de cada ventana.",
            "Evaluar y registrar el desempeño de cada subcontratista.",
        ],
    },
    "PROYECTO": {
        "porques": [
            "¿Por qué se frena? Falta información o definición de proyecto.",
            "¿Por qué falta? Las consultas a la inspección o ingeniería demoran en resolverse.",
            "¿Por qué demoran? No hay un circuito formal con plazos de respuesta.",
            "¿Por qué no hay circuito? Las consultas se hacen por canales informales.",
            "Causa raíz probable: gestión de consultas (RFI) y cambios sin circuito formal ni plazos de respuesta.",
        ],
        "acciones": [
            "Implementar registro de consultas (RFI) con plazo de respuesta acordado.",
            "Revisar planos de las próximas 3 semanas antes de liberar tareas ('liberación de restricciones').",
            "Formalizar el circuito de órdenes de cambio.",
        ],
    },
    "INTERFERENCIAS": {
        "porques": [
            "¿Por qué se frena? Hay interferencia con servicios, terceros o falta un permiso.",
            "¿Por qué no se previó? El relevamiento previo de servicios fue incompleto.",
            "¿Por qué incompleto? No se gestionaron permisos y relevamientos antes del inicio.",
            "¿Por qué no se gestionaron? No hay checklist de restricciones por frente de obra.",
            "Causa raíz probable: falta de análisis de restricciones y gestión anticipada de permisos e interferencias.",
        ],
        "acciones": [
            "Checklist de restricciones (permisos, servicios, accesos) por frente antes de liberar la tarea.",
            "Gestionar permisos municipales y de empresas de servicios con anticipación.",
            "Relevamiento de servicios enterrados previo a excavaciones.",
        ],
    },
    "SEGURIDAD": {
        "porques": [
            "¿Por qué se detiene? Una condición o inspección de seguridad frena la tarea.",
            "¿Por qué hay condiciones inseguras? Las condiciones no se verifican antes de iniciar.",
            "¿Por qué no se verifican? No hay inspección previa estandarizada por tarea.",
            "¿Por qué no está estandarizada? Los análisis de riesgo no se hacen por actividad.",
            "Causa raíz probable: análisis de riesgo por tarea ausente o no integrado a la planificación.",
        ],
        "acciones": [
            "Análisis de seguridad por tarea (AST) antes de iniciar actividades de riesgo.",
            "Checklist de andamios, EPP y condiciones del frente.",
            "Capacitar al personal nuevo antes de asignarlo a tareas críticas.",
        ],
    },
    "CALIDAD": {
        "porques": [
            "¿Por qué no se cumple lo planificado? Se rehace o se corrige trabajo ya ejecutado.",
            "¿Por qué se rehace? El trabajo no cumplió el ensayo o la inspección.",
            "¿Por qué no cumplió? Faltó control durante la ejecución.",
            "¿Por qué faltó control? Los controles se hacen al final y no durante la tarea.",
            "Causa raíz probable: controles de calidad al final de la tarea en lugar de durante la ejecución.",
        ],
        "acciones": [
            "Controles intermedios con checklist por actividad (hacerlo bien a la primera).",
            "Coordinar ensayos antes de ejecutar la etapa siguiente.",
            "Registrar y analizar retrabajos para atacar su causa.",
        ],
    },
    "OTROS": {
        "porques": [
            "Las descripciones no permiten identificar una causa clara.",
            "Se recomienda mejorar la calidad del registro de partes diarios.",
        ],
        "acciones": [
            "Capacitar a capataces en el registro de causas con una lista cerrada.",
            "Revisar manualmente los desvíos marcados para revisión.",
        ],
    },
    "SIN_CAUSA": {
        "porques": [
            "Hay desvíos que no tienen causa registrada en el parte diario.",
            "Sin causa no se puede priorizar ni mejorar: es el primer problema de proceso a resolver.",
        ],
        "acciones": [
            "Hacer obligatorio el campo causa cuando se ejecuta menos de lo planificado.",
            "Usar una lista desplegable de causas en el parte (estandariza y evita texto libre ambiguo).",
        ],
    },
}

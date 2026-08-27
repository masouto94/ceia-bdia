# Reporte de entrenamiento — Clasificador de intención en tickets de soporte (NLP)

## Resumen ejecutivo

El equipo de NLP del tenant Beta entrenó un modelo de clasificación de texto para categorizar automáticamente tickets de soporte técnico según la intención del usuario (reclamo, consulta, solicitud de reembolso, problema técnico, elogio). El objetivo es enrutar automáticamente cada ticket al equipo correspondiente sin intervención manual, reduciendo el tiempo de primera respuesta.

## Dataset

- **Nombre**: `support-tickets-es-v2`
- **Total de ejemplos**: 26.500 tickets (entrenamiento: 21.200 / validación: 2.650 / test: 2.650)
- **Idioma**: español (variantes rioplatense y neutro)
- **Clases**: `reclamo`, `consulta_general`, `solicitud_reembolso`, `problema_tecnico`, `elogio`
- **Longitud promedio**: 47 tokens por ticket
- **Fuente**: histórico anonimizado de mesa de ayuda, con etiquetado supervisado por el equipo de soporte

## Arquitectura y configuración

- **Modelo base**: `bert-base-multilingual-cased`, fine-tuning con cabeza de clasificación
- **Framework**: HuggingFace Transformers + PyTorch
- **Optimización**: AdamW, learning rate 2e-5, warmup lineal de 500 pasos
- **Batch size**: 32
- **Épocas**: 6 (early stopping en época 4 por overfitting)
- **Tokenización**: WordPiece, longitud máxima 128 tokens

## Resultados

| Métrica | Entrenamiento | Validación | Test |
| --- | --- | --- | --- |
| Accuracy | 0.962 | 0.918 | 0.912 |
| F1-score (macro) | 0.958 | 0.903 | 0.897 |
| Precisión (clase `problema_tecnico`) | 0.95 | 0.88 | 0.86 |
| Recall (clase `solicitud_reembolso`) | 0.93 | 0.86 | 0.84 |

La mayor confusión se dio entre `reclamo` y `problema_tecnico`, ya que muchos tickets combinan ambas intenciones en el mismo texto (ej. "no funciona y quiero que me devuelvan la plata").

## Conclusiones y próximos pasos

- El modelo cumple el umbral mínimo de aceptación (90% accuracy en test) para pasar a un piloto controlado con el 10% del tráfico real.
- Se recomienda evaluar una salida multi-etiqueta (en vez de clase única) para los tickets que mezclan intenciones.
- Próximo experimento planificado: comparar contra un modelo más liviano (DistilBERT multilingüe) para reducir latencia de inferencia en producción.

# Reporte de entrenamiento — Clasificador de defectos en piezas metálicas (visión)

## Resumen ejecutivo

El equipo de Visión por Computadora del tenant Alpha entrenó un modelo de clasificación de imágenes para detectar defectos superficiales (rayas, poros, deformaciones) en piezas metálicas fabricadas en línea. El objetivo es reemplazar la inspección visual manual en la línea de control de calidad, reduciendo el tiempo de inspección por pieza de 12 segundos a menos de 2 segundos.

## Dataset

- **Nombre**: `metal-defects-v3`
- **Total de imágenes**: 18.420 (entrenamiento: 14.740 / validación: 1.840 / test: 1.840)
- **Clases**: `sin_defecto`, `rayadura`, `poro`, `deformacion`, `oxido`
- **Resolución**: 512x512 px, normalizadas a RGB
- **Fuente**: cámaras industriales en 3 líneas de producción, etiquetado manual con doble revisión

## Arquitectura y configuración

- **Modelo base**: ResNet-50 preentrenado en ImageNet, fine-tuning completo
- **Framework**: PyTorch 2.2
- **Optimización**: AdamW, learning rate 3e-4 con cosine annealing
- **Batch size**: 64
- **Épocas**: 40 (early stopping en época 33 por plateau de validación)
- **Aumentación de datos**: flip horizontal, rotación ±15°, jitter de brillo/contraste

## Resultados

| Métrica | Entrenamiento | Validación | Test |
| --- | --- | --- | --- |
| Accuracy | 0.978 | 0.941 | 0.936 |
| F1-score (macro) | 0.971 | 0.928 | 0.921 |
| Precisión (clase `poro`) | 0.96 | 0.89 | 0.87 |
| Recall (clase `poro`) | 0.94 | 0.85 | 0.83 |

La clase con mayor confusión fue `poro` vs `oxido`, con 47 casos mal clasificados en el set de test, atribuidos a similitud visual en piezas con iluminación deficiente.

## Conclusiones y próximos pasos

- El modelo supera el umbral mínimo de aceptación (90% accuracy en test) definido por el equipo de calidad.
- Se recomienda ampliar el dataset con más ejemplos de `poro` bajo distintas condiciones de iluminación antes de pasar a producción.
- Próximo experimento planificado: probar arquitectura EfficientNet-B3 para comparar costo computacional vs. accuracy en el borde (edge deployment en la línea de producción).

# Guía del Proyecto — Caneca Furada (CLAUDE.md)

Este archivo define las reglas de desarrollo para el repositorio.
- **Fuente de verdad:** El **prompt maestro** rige los requisitos funcionales, la arquitectura objetivo y las decisiones específicas de Caneca Furada.
- **Alcance:** Los **prompts de fase** determinan el alcance concreto de cada tarea.
- **Conflicto de especificaciones:** Si detectas contradicciones entre documentos, **detente, identifica la contradicción y solicita una decisión**; no elijas silenciosamente una interpretación.

---

## 1. Antes de modificar código
1. **Inspección inicial:** Inspecciona el repositorio, las instrucciones aplicables, `README`, documentación, dependencias, modelos, migraciones, tests y estado de Git.
2. **Verificación real:** Determina qué existe realmente; no supongas que una funcionalidad descrita en el prompt maestro ya está implementada.
3. **Planificación:** Identifica la fase solicitada, sus dependencias, criterios de aceptación y archivos afectados. Propón un plan breve y acotado antes de realizar cambios relevantes.
4. **Toma de decisiones:** Si una decisión bloqueante no está especificada, pregunta. Para decisiones menores, adopta la opción más sencilla y coherente y documenta el motivo.
5. **Respeto al entorno:** No sobrescribas cambios del usuario ni reviertas trabajo ajeno. No ejecutes acciones destructivas ni operaciones sobre producción sin autorización.

---

## 2. Alcance y diseño
- **Enfoque acotado:** Implementa únicamente la fase solicitada y las dependencias estrictamente necesarias.
- **Limpieza de arquitectura:** Reutiliza las convenciones y componentes del repositorio. Evita refactorizaciones no relacionadas, dependencias innecesarias y complejidad prematura.
- **Separación de responsabilidades:** Mantén una separación clara entre presentación, validación, autorización y lógica de negocio.
- **Módulos de dominio:** Coloca las reglas de negocio reutilizables en servicios o módulos de dominio; no las dupliques entre plantillas, vistas, tareas y API.
- **Base de datos:** Protege las invariantes importantes también en la base de datos cuando sea apropiado.
- **Migraciones:** Mantén las migraciones pequeñas y revisables. Antes de cambiar modelos de usuario o migraciones existentes, analiza el impacto y documenta la estrategia.
- **Veracidad:** No afirmes que una integración, envío, despliegue o prueba se ha realizado si no hay evidencia.

---

## 3. Seguridad y privacidad
Aplica seguridad desde el diseño y el principio de mínimo privilegio en cada fase.
- **Validación en Servidor:** Valida los datos en el servidor; no confíes en roles, permisos, saldos, puntos, precios ni estados sensibles enviados por el cliente. Ocultar botones en la interfaz no sustituye los controles del servidor.
- **Autorización:** Verifica autorización en cada operación y sobre cada objeto. Añade pruebas para accesos denegados y escalada de privilegios, además de los casos permitidos.
- **Protección activa:** Protege frente a CSRF, XSS, inyección, IDOR/BOLA, asignación masiva, abuso de endpoints y operaciones duplicadas.
- **Cero Secretos / PII:** No guardes secretos, contraseñas, tokens reales ni datos personales reales en el repositorio, tests, ejemplos, capturas o documentación. No expongas datos personales en URLs, QR, logs, analítica ni mensajes de error. Evita registrar tokens o enlaces de recuperación/verificación.
- **Exposición mínima:** Devuelve explícitamente solo los campos necesarios en vistas y serializadores.
- **Mecanismos nativos:** Usa los mecanismos de seguridad de Django y dependencias mantenidas; no implementes criptografía propia.
- **Gestión de riesgos:** No desactives controles de seguridad para resolver un problema sin explicar el riesgo y ofrecer una alternativa segura. Documenta riesgos y medidas adoptadas. No presentes el código como garantía automática de cumplimiento legal.

---

## 4. Integridad de datos y operaciones críticas
Cuando una tarea afecte a puntos, compras, recompensas, canjes, verificación de email, permisos u otra operación sensible:
- Diseña la operación para ser atómica y segura frente a concurrencia.
- Evita duplicados con restricciones únicas, idempotencia o mecanismos equivalentes.
- Valida reglas de negocio en el servidor y vuelve a comprobar condiciones críticas dentro de la transacción.
- Mantén trazabilidad de acciones administrativas sin registrar secretos ni datos innecesarios.
- Evita modificar o borrar historiales para corregirlos; utiliza movimientos compensatorios cuando corresponda al diseño aprobado.
- Añade pruebas de límites, reintentos, doble envío, doble consumo y concurrencia cuando sean relevantes.

---

## 5. Calidad y pruebas
1. Añade o actualiza tests para el comportamiento nuevo, errores esperados y permisos.
2. Ejecuta las comprobaciones disponibles y pertinentes.
3. Revisa el diff para detectar regresiones, cambios fuera de alcance, secretos, datos personales en logs y documentación desactualizada.
4. Informa de los resultados reales.

Utiliza las herramientas ya configuradas. No instales herramientas adicionales sin una razón clara. Si no puedes ejecutar una prueba, indica cuál y por qué. Nunca marques como superada una prueba que no se haya ejecutado.

Comprobaciones Django habituales, si son aplicables:
```bash
python manage.py check
python manage.py test
```

---

## 6. Documentación obligatoria por tarea o fase
Actualiza la documentación junto con el código. Reutiliza la estructura existente; no crees archivos duplicados si ya hay un lugar equivalente.

Para cada fase relevante, documenta:
- Objetivo, alcance, exclusiones y criterios de aceptación.
- Decisiones técnicas y motivo de las decisiones no obvias.
- Archivos, modelos, servicios, rutas, plantillas y migraciones modificados.
- Configuración necesaria y variables de entorno nuevas o modificadas, sin secretos.
- Instrucciones reproducibles de uso, instalación u operación cuando proceda.
- Tests añadidos, comandos ejecutados y resultados reales.
- Consideraciones de seguridad y privacidad.
- Limitaciones, dependencias externas, riesgos y tareas pendientes.
- Estado de cada criterio de aceptación y dependencias para la fase siguiente.

Mantén `README.md` como punto de entrada y enlaza a documentación detallada. Usa datos ficticios en los ejemplos.
Guarda la documentación además de en el `README.md` en un archivo `.md` dentro de `docs/`.

---

## 7. Definición de terminado (Done)
No declares una tarea o fase completa solo porque se haya escrito el código. Verifica que:
- El alcance acordado está implementado o las excepciones están documentadas.
- La validación y autorización se realizan en servidor.
- Las migraciones, si existen, están revisadas.
- Los tests pertinentes se han ejecutado y sus resultados se comunican con precisión.
- La documentación correspondiente está actualizada en `docs/` y `README.md`.
- No se han añadido secretos ni datos personales reales.
- Las limitaciones y acciones manuales pendientes están identificadas.

Usa estados claros: **Pendiente**, **En curso**, **Bloqueada** o **Completa**.

---

## 8. Formato de respuesta al finalizar
Responde en español, de forma clara y sin repetir grandes bloques de código. Incluye:
1. **Resultado y estado** de la tarea/fase.
2. **Cambios principales** y archivos relevantes.
3. **Pruebas ejecutadas**, comandos exactos y resultados reales.
4. **Documentación actualizada**.
5. **Configuración o acciones manuales** necesarias.
6. **Limitaciones, riesgos y pendientes**.
7. **Siguiente paso recomendado**, alineado con el plan de fases.

Si encuentras una vulnerabilidad grave, una migración arriesgada o una contradicción entre instrucciones, detente antes de ampliar el cambio y explica el problema.

**Prioridad:** respetar los requisitos aprobados, proteger los datos, preservar la integridad del sistema y dejar código comprobable y documentado.
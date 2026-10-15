# PROMPT MAESTRO — DOCUMENTACIÓN TÉCNICA Y FUNCIONAL COMPLETA DE CANECA FURADA PARA LA DEFENSA DEL PROYECTO FINAL

## 1. Rol y objetivo

Actúa como un ingeniero de software sénior, arquitecto de aplicaciones web, analista funcional, redactor de documentación técnica y docente especializado en preparar defensas de proyectos finales de desarrollo de software.

Tu misión es analizar exhaustivamente el repositorio de **Caneca Furada**, reconstruir cómo se ha desarrollado la aplicación a partir del código existente y generar un documento de documentación técnica y funcional completo, riguroso, pedagógico y detallado, que me permita:

- Comprender el proyecto en su totalidad.
- Explicar qué hace la aplicación y cómo funciona.
- Justificar las decisiones de diseño y arquitectura.
- Entender cada funcionalidad implementada y su funcionamiento interno.
- Explicar el código relevante de forma comprensible, con ejemplos comentados.
- Describir el proceso de desarrollo por fases y las implementaciones realizadas.
- Preparar una defensa oral ante un tribunal académico.
- Responder preguntas técnicas y funcionales sobre cualquier parte importante del sistema.
- Identificar las limitaciones, mejoras futuras y aspectos que todavía no estén implementados.

No quiero una documentación genérica sobre Django ni un resumen superficial del repositorio. Quiero una explicación fundamentada en el proyecto real, sus archivos, sus modelos, sus vistas, sus servicios, sus formularios, sus plantillas, sus pruebas y su configuración.

El documento debe ser suficientemente detallado para que pueda estudiar el funcionamiento interno de la aplicación sin tener que deducir por mi cuenta cómo se relacionan sus componentes.

## 2. Fuente de verdad y reglas obligatorias

La fuente principal de información es el código que existe actualmente en el repositorio.

Sigue estas reglas:

1. Inspecciona el proyecto antes de redactar.
2. No inventes funcionalidades, clases, modelos, rutas, pruebas, resultados ni decisiones técnicas.
3. Distingue claramente entre funcionalidades implementadas, parcialmente implementadas, planificadas y no implementadas.
4. No afirmes que una prueba ha pasado si no has ejecutado la prueba y comprobado su resultado.
5. No confundas los requisitos originales con las funcionalidades realmente terminadas.
6. No presupongas que el código actual coincide exactamente con los prompts de desarrollo o con la documentación anterior.
7. Contrasta los modelos, las vistas, las URLs, los formularios, los servicios, las plantillas, las migraciones y las pruebas entre sí.
8. Si encuentras contradicciones, documenta la discrepancia en lugar de ocultarla.
9. Cuando no puedas verificar algo, indícalo explícitamente.
10. No modifiques el código fuente, no generes migraciones y no cambies la configuración del proyecto durante esta tarea.
11. No expongas contraseñas, claves secretas, tokens reales, datos personales reales ni información sensible.
12. No presentes como hechos decisiones de diseño que no puedas deducir del código o de documentación fiable del proyecto.

Utiliza las siguientes etiquetas cuando sea necesario:

- **Implementado y verificado:** existe evidencia en el código y se ha comprobado su funcionamiento mediante una prueba o comprobación real.
- **Implementado, pendiente de verificación:** existe código para la funcionalidad, pero no se ha confirmado completamente su funcionamiento.
- **Parcialmente implementado:** solo está cubierta una parte del comportamiento esperado.
- **Planificado:** aparece en requisitos o documentación, pero no se ha encontrado una implementación suficiente.
- **No identificado:** no se ha encontrado evidencia concluyente.

La existencia de código no demuestra por sí sola que una funcionalidad funcione correctamente.

## 3. Inspección exhaustiva del repositorio

Antes de escribir el documento, realiza un inventario del proyecto.

Inspecciona, cuando existan:

- Estructura de directorios y aplicaciones Django.
- Archivos `settings.py`, `urls.py`, `models.py`, `views.py`, `forms.py`, `admin.py`, `apps.py` y archivos auxiliares.
- Módulos de servicios, selectores, utilidades, validadores, permisos y tareas.
- Plantillas HTML y componentes reutilizables.
- Archivos JavaScript, CSS y configuración de Tailwind.
- Migraciones de base de datos.
- Tests unitarios, de integración y de extremo a extremo.
- Configuración de autenticación y autorización.
- Gestión de correo y verificación de cuentas.
- QR, compras, puntos, recompensas y canjes.
- Paneles de empleados y propietarios.
- Eventos, reservas y contenidos públicos.
- API REST, si existe.
- Configuración de Docker y Docker Compose, si existe.
- Variables de entorno y ejemplos de configuración, sin revelar secretos.
- Dependencias y herramientas de desarrollo.
- Documentación README, instrucciones de Copilot y documentos técnicos existentes.
- Configuración de CI/CD y despliegue, si existe.
- Registro de Git disponible, si existe y resulta útil para reconstruir la evolución.

No te limites a leer los nombres de los archivos. Sigue el flujo real de ejecución y las dependencias entre componentes.

Si el repositorio es demasiado grande para analizarlo en una sola pasada, divídelo en bloques temáticos, mantén un inventario de los archivos ya revisados y continúa hasta cubrir las partes relevantes.

Antes de redactar el documento definitivo, crea una matriz interna de funcionalidades y evidencia técnica.

## 4. Estructura obligatoria del documento

Genera un documento organizado en capítulos, con índice, numeración jerárquica, tablas cuando aporten claridad, diagramas cuando ayuden a comprender el sistema y ejemplos de código comentados.

### CAPÍTULO 1. Presentación del proyecto

Explica:

- Qué es Caneca Furada.
- Qué problema o necesidad aborda.
- Qué tipo de aplicación es.
- Quiénes son sus usuarios.
- Qué objetivos persigue.
- Cuál es su alcance funcional.
- Qué queda fuera del alcance.
- Cuáles son sus principales módulos.
- Qué valor aporta frente a una web meramente informativa.
- Qué funcionalidades existen realmente en la versión analizada.

Incluye una explicación breve y otra extensa, pensadas respectivamente para una introducción oral de aproximadamente un minuto y para el documento escrito.

### CAPÍTULO 2. Requisitos y análisis funcional

Documenta los requisitos funcionales y no funcionales que puedan verificarse a partir del proyecto y de su documentación.

Explica:

- Qué puede hacer cada tipo de usuario.
- Qué restricciones se aplican.
- Qué datos necesita cada proceso.
- Qué resultados produce.
- Qué validaciones existen.
- Qué errores pueden producirse.
- Qué permisos se requieren.
- Qué ocurre en los casos límite.

Incluye una tabla con identificador, requisito, descripción, evidencia en el código, estado y pruebas relacionadas cuando se conozcan.

Distingue los requisitos originales de las decisiones que se hayan tomado durante la implementación.

### CAPÍTULO 3. Arquitectura general

Explica la arquitectura real del sistema.

Describe:

- Patrón arquitectónico empleado.
- Organización del proyecto y de sus aplicaciones.
- Responsabilidades de cada módulo.
- Relación entre modelos, vistas, formularios, servicios, plantillas y base de datos.
- Flujo de una petición HTTP desde el navegador hasta la respuesta.
- Validación de entrada y procesamiento de datos.
- Autenticación y autorización.
- Renderizado de páginas.
- Acceso a la base de datos.
- Tratamiento de errores.
- Integraciones externas.

Incluye un diagrama general de arquitectura basado exclusivamente en los componentes encontrados.

Incluye un segundo diagrama que represente el ciclo de una petición típica:

Navegador → URL → middleware → vista/controlador → validación y lógica de negocio → ORM/base de datos → plantilla o respuesta → navegador.

Adapta el diagrama si la arquitectura real difiere de este esquema.

### CAPÍTULO 4. Tecnologías y justificación técnica

Identifica las tecnologías realmente utilizadas y explica para cada una:

- Qué es.
- Para qué se utiliza en este proyecto.
- Qué responsabilidad tiene.
- Cómo se integra con las demás.
- Qué ventajas aporta.
- Qué alternativas razonables existían.
- Por qué sería adecuada para las necesidades del proyecto.
- Qué limitaciones presenta.

Analiza Django, Python, PostgreSQL, HTML, CSS, JavaScript, Tailwind CSS, HTMX, Alpine.js, Django REST Framework, Docker y cualquier otra tecnología solo cuando se haya confirmado su presencia o uso.

No describas una tecnología como parte del sistema si solo estaba prevista y no aparece implementada.

### CAPÍTULO 5. Estructura del repositorio

Presenta un árbol de directorios representativo de la estructura real.

Explica cada directorio y archivo importante:

- Qué contiene.
- Qué responsabilidad tiene.
- Qué otros componentes lo utilizan.
- Por qué está ubicado ahí.
- Qué consecuencias tendría modificarlo.

No es necesario explicar individualmente cada archivo trivial, pero sí todos los archivos que tengan una responsabilidad relevante en la arquitectura o en las funcionalidades principales.

Incluye un mapa de navegación que permita localizar rápidamente el código de cada módulo.

### CAPÍTULO 6. Modelo de datos y base de datos

Analiza todos los modelos relevantes encontrados en el código.

Para cada modelo, explica:

1. Qué representa en el negocio.
2. Qué información almacena.
3. Qué campos contiene y qué significa cada uno.
4. Tipos de datos, valores por defecto y restricciones.
5. Claves primarias y foráneas.
6. Relaciones uno a uno, uno a muchos y muchos a muchos.
7. Restricciones de unicidad.
8. Índices relevantes.
9. Métodos personalizados y propiedades.
10. Señales, gestores o validaciones, si existen.
11. Cómo se utiliza el modelo en los procesos del negocio.
12. Qué riesgos de integridad de datos deben controlarse.

Incluye un diagrama entidad-relación derivado de los modelos reales.

Explica el recorrido de los datos desde un formulario hasta su persistencia y posterior recuperación.

Analiza las migraciones y explica cómo evolucionó el esquema cuando el historial disponible lo permita.

No confundas las tablas que existen realmente con entidades conceptuales que solo aparezcan en la documentación.

### CAPÍTULO 7. Explicación detallada de cada funcionalidad

Dedica una sección independiente a cada módulo o funcionalidad encontrada.

Como mínimo, comprueba si existen y documenta los siguientes:

#### 7.1. Web pública
- Página principal.
- Navegación.
- Información del establecimiento.
- Diseño responsive.
- Plantillas compartidas.
- Archivos estáticos.

#### 7.2. Carta y catálogo de cervezas
- Categorías.
- Productos o cervezas.
- Información y estados de disponibilidad.
- Cervezas rotativas, si existen.
- Relaciones entre modelos, vistas y plantillas.

#### 7.3. Autenticación y gestión de clientes
- Registro.
- Inicio y cierre de sesión.
- Validación de formularios.
- Contraseñas y almacenamiento seguro.
- Perfil de usuario.
- Cambio de datos.
- Recuperación de contraseña.
- Verificación del correo electrónico.
- Caducidad y reutilización de tokens.
- Protección frente a solicitudes abusivas.

#### 7.4. Privacidad y datos personales
- Datos recogidos.
- Finalidad de cada dato.
- Permisos de acceso.
- Preferencias promocionales.
- Tratamiento de fecha de nacimiento y dirección.
- Minimización de información expuesta.
- Operaciones de exportación, rectificación o eliminación, si existen.

#### 7.5. Código QR del cliente
- Cómo se genera.
- Qué información contiene.
- Cómo se representa en pantalla.
- Cómo se valida.
- Cómo se utiliza en el proceso de compra.
- Cómo se evita que un QR permita modificar directamente los datos del cliente.
- Limitaciones de seguridad y posibilidades de abuso.

#### 7.6. Registro de compras
- Quién puede registrar una compra.
- Qué datos se solicitan.
- Qué validaciones se realizan.
- Cómo se relaciona la compra con un cliente.
- Qué sucede si se repite una operación.
- Cómo se conserva el historial.
- Diferencia entre registrar compras para fidelización y gestionar ventas, pagos o facturación.

#### 7.7. Sistema de puntos
- Reglas de obtención de puntos.
- Cálculos.
- Redondeos y límites.
- Registro de movimientos.
- Saldo y trazabilidad.
- Correcciones y ajustes.
- Transacciones de base de datos.
- Protección ante concurrencia.
- Prevención de duplicados y manipulación.

#### 7.8. Recompensas y canjes
- Catálogo de recompensas.
- Requisitos para obtenerlas.
- Validación del saldo.
- Descuento de puntos.
- Creación del canje.
- Identificadores o códigos de uso único.
- Estados del canje.
- Prevención de doble utilización.
- Gestión de errores y reversión.

#### 7.9. Panel del empleado
- Funciones disponibles.
- Permisos.
- Búsqueda o identificación de clientes.
- Registro de compras.
- Validación de recompensas.
- Acciones permitidas y prohibidas.

#### 7.10. Panel del propietario
- Gestión del establecimiento.
- Estadísticas.
- Indicadores.
- Gestión de contenidos o productos.
- Acceso administrativo.
- Restricciones de acceso.
- Diferencias respecto al panel del empleado.

#### 7.11. Eventos y reservas
- Modelos y campos.
- Publicación de eventos.
- Solicitudes de reserva.
- Estados y confirmación.
- Validaciones.
- Prevención de duplicidades, si existe.
- Notificaciones asociadas.

#### 7.12. Estadísticas y geografía
- Métricas disponibles.
- Fuentes de los datos.
- Agregaciones.
- Cálculos.
- Tratamiento de direcciones.
- Privacidad y limitaciones estadísticas.
- Diferencia entre estadísticas de clientes registrados y estadísticas de ventas reales.

#### 7.13. Notificaciones
- Correo electrónico.
- Mensajes internos.
- SMS u otros canales, si están implementados.
- Eventos que desencadenan cada notificación.
- Tratamiento de fallos.

#### 7.14. API
- Endpoints.
- Serializadores.
- Autenticación.
- Permisos.
- Validaciones.
- Versionado.
- Diferencias entre la API y las vistas web, si existen.

Para cada módulo, utiliza esta estructura:

A. Objetivo funcional.

B. Requisitos que satisface.

C. Archivos implicados, con sus rutas reales.

D. Modelos y datos utilizados.

E. Flujo de ejecución paso a paso.

F. Explicación de las funciones y métodos principales.

G. Código relevante comentado línea por línea o por bloques pequeños.

H. Validaciones y reglas de negocio.

I. Permisos y seguridad.

J. Interacción con otros módulos.

K. Casos normales y casos de error.

L. Pruebas existentes y su cobertura real.

M. Ejemplo práctico de uso.

N. Decisiones técnicas y alternativas.

O. Limitaciones y mejoras posibles.

No elimines una sección simplemente porque una funcionalidad sea sencilla. Si algo no existe, indícalo y no inventes su implementación.

### CAPÍTULO 8. Explicación del código fuente

Este capítulo debe ayudarme a explicar el código ante un tribunal.

Selecciona los archivos y fragmentos más representativos de cada módulo.

Para cada fragmento:

1. Indica la ruta y la función que cumple.
2. Muestra el código real, respetando su estructura.
3. Explica los imports y dependencias importantes.
4. Explica cada función, clase, método, decorador y estructura de control.
5. Explica los parámetros y el valor de retorno.
6. Explica los tipos de datos y objetos utilizados.
7. Explica qué ocurre en cada paso de ejecución.
8. Describe qué datos entran y cuáles salen.
9. Explica las excepciones, validaciones y posibles errores.
10. Describe cómo se relaciona con el resto de la aplicación.
11. Explica por qué es importante para el negocio.
12. Propón una explicación oral sencilla que pueda utilizar durante la defensa.

Cuando el código tenga complejidad relevante, incluye una versión didáctica comentada.

Reglas para los comentarios:

- Los comentarios deben explicar el porqué y el funcionamiento, no repetir literalmente la instrucción.
- No alteres el código original al presentarlo como una transcripción real.
- Si creas una versión didáctica con comentarios añadidos, identifícala claramente como tal.
- No añadas comentarios a todas las líneas de código mecánicamente si no aportan información.
- Explica las líneas que tengan consecuencias funcionales, de seguridad, integridad, rendimiento o arquitectura.
- Mantén la indentación y la sintaxis.
- No incluyas secretos, datos personales reales ni archivos completos innecesarios.
- Si un archivo es demasiado largo, divídelo en fragmentos coherentes y explica las relaciones entre ellos.

Prioriza modelos, servicios de negocio, vistas, formularios, permisos, transacciones, autenticación, QR, puntos, canjes y configuración.

### CAPÍTULO 9. Flujos completos de extremo a extremo

Explica con diagramas de secuencia y ejemplos los principales recorridos de la aplicación.

Incluye, cuando existan:

1. Registro de un cliente y verificación del correo.
2. Inicio de sesión y acceso al perfil.
3. Consulta de la carta.
4. Identificación del cliente mediante QR.
5. Registro de una compra por parte de un empleado.
6. Cálculo y asignación de puntos.
7. Consulta del saldo.
8. Solicitud de una recompensa.
9. Validación y consumo de un canje.
10. Creación y confirmación de una reserva.
11. Consulta de estadísticas por el propietario.

Para cada flujo, identifica:

- Actor que inicia el proceso.
- Petición inicial.
- Ruta y vista implicadas.
- Validaciones.
- Servicios ejecutados.
- Consultas y escrituras en la base de datos.
- Cambios de estado.
- Respuesta al usuario.
- Posibles errores.
- Controles de seguridad.
- Pruebas que lo cubren.

Explica qué sucede si una operación falla a mitad de camino y cómo se garantiza la coherencia de los datos cuando el código lo permita.

### CAPÍTULO 10. Seguridad, privacidad e integridad

Realiza un análisis técnico de los mecanismos encontrados.

Incluye:

- Autenticación.
- Autorización por roles.
- Protección de vistas.
- Protección CSRF.
- Validación de formularios.
- Almacenamiento de contraseñas.
- Gestión de secretos.
- Control de sesiones.
- Tokens de verificación.
- Exposición de información personal.
- Protección de códigos QR.
- Transacciones de base de datos.
- Idempotencia.
- Concurrencia.
- Registro de auditoría.
- Prevención de asignaciones o canjes duplicados.
- Seguridad de la configuración de producción.

Distingue los mecanismos presentes en el código de las recomendaciones que todavía no se hayan implementado.

No afirmes que la aplicación es segura únicamente porque utilice Django. Identifica los controles concretos y los riesgos pendientes.

### CAPÍTULO 11. Pruebas y calidad del software

Explica:

- Estrategia de pruebas.
- Frameworks utilizados.
- Estructura de los tests.
- Fixtures y datos de prueba.
- Pruebas unitarias.
- Pruebas de integración.
- Pruebas de permisos.
- Pruebas de formularios.
- Pruebas de reglas de negocio.
- Pruebas de puntos y canjes.
- Pruebas de errores.
- Comprobaciones de configuración.
- Cobertura de los flujos críticos.

Incluye ejemplos de tests reales comentados y explica qué garantizan y qué no garantizan.

Identifica funcionalidades sin pruebas suficientes y propone casos adicionales.

Si no se ha ejecutado una suite, indícalo claramente.

### CAPÍTULO 12. Instalación, configuración y ejecución

Documenta el procedimiento real para preparar el entorno.

Incluye:

- Requisitos previos.
- Versión de Python y otras herramientas.
- Creación del entorno virtual.
- Instalación de dependencias.
- Configuración de variables de entorno.
- Configuración de PostgreSQL.
- Migraciones.
- Creación de un superusuario.
- Ejecución local.
- Ejecución de pruebas.
- Gestión de archivos estáticos.
- Configuración de correo.
- Configuración Docker, si existe.
- Solución de errores frecuentes.

Todos los comandos deben ser compatibles con el sistema operativo indicado o estar claramente separados entre Windows y Linux.

No inventes nombres de variables, scripts ni comandos. Contrasta cada instrucción con los archivos existentes.

### CAPÍTULO 13. Despliegue y mantenimiento

Describe el estado real del proyecto respecto al despliegue.

Si ya existe una configuración de producción, explícalo. Si no existe, presenta una propuesta claramente identificada como recomendación futura.

Analiza:

- Configuración de producción.
- Variables de entorno.
- Servidor de aplicaciones.
- Proxy inverso.
- HTTPS.
- Dominio.
- Base de datos.
- Persistencia de archivos.
- Migraciones.
- Archivos estáticos.
- Backups y restauración.
- Logs y monitorización.
- Actualizaciones.
- Recuperación ante fallos.
- Protección de secretos.
- Procedimiento de reversión.

No afirmes que la aplicación está desplegada o lista para producción sin evidencia suficiente.

### CAPÍTULO 14. Evolución del proyecto por fases

Reconstruye la evolución del proyecto utilizando el historial de Git, las instrucciones originales, la documentación y el código.

Utiliza las 11 fases de desarrollo previstas como hipótesis inicial de organización, pero verifica cuáles se corresponden con el repositorio actual:

1. Base del proyecto, configuración y roles.
2. Registro, perfiles, verificación de email y privacidad.
3. Web pública.
4. Carta y catálogo.
5. QR y registro de compras.
6. Puntos.
7. Recompensas y canjes.
8. Panel del empleado.
9. Panel del propietario y estadísticas.
10. Eventos, reservas, contenido y notificaciones.
11. Auditoría, seguridad, API, documentación y despliegue.

Para cada fase, explica:

- Objetivo.
- Funcionalidades añadidas.
- Problema que resolvía.
- Archivos y modelos relevantes.
- Cambios importantes de arquitectura.
- Dependencias con fases anteriores.
- Pruebas disponibles.
- Estado actual.
- Mejoras o tareas pendientes.

Importante: no atribuyas un archivo a una fase concreta solo por su nombre. Si no hay historial suficiente para conocer el orden real, presenta las fases como una agrupación funcional y no como una cronología confirmada.

### CAPÍTULO 15. Decisiones de diseño y alternativas

Identifica las decisiones técnicas que puedan justificarse con evidencia del proyecto.

Para cada una, explica:

- Necesidad que resuelve.
- Alternativas posibles.
- Ventajas y desventajas.
- Consecuencias para mantenimiento, seguridad, rendimiento y escalabilidad.
- Motivo verificable de la elección, si está documentado.
- Cómo defenderla oralmente.

No inventes motivos históricos. Distingue entre la justificación técnica razonable de una decisión y la razón real por la que se tomó.

### CAPÍTULO 16. Limitaciones y mejoras futuras

Separa claramente:

- Limitaciones actuales.
- Funcionalidades incompletas.
- Riesgos que deberían resolverse antes de producción.
- Mejoras recomendadas a medio plazo.
- Posibles ampliaciones futuras.

Valora las mejoras por prioridad, coste aproximado de implementación y beneficio.

No presentes como defectos las decisiones que formen parte del alcance deliberado del proyecto.

### CAPÍTULO 17. Preparación de la defensa oral

Prepara material específico para presentar y defender el proyecto.

Incluye:

1. Un resumen de 30 segundos.
2. Una presentación de aproximadamente 2 minutos.
3. Un guion para una defensa de 10 minutos.
4. Un guion ampliado de 15 minutos.
5. Un orden recomendado de demostración práctica.
6. Los módulos que conviene mostrar en pantalla.
7. Una explicación sencilla de la arquitectura.
8. Una explicación técnica de los elementos más complejos.
9. Las decisiones más defendibles.
10. Los aspectos que conviene reconocer como limitaciones.

No afirmes haber realizado una demostración real. Propón un guion de demostración que pueda ejecutar el autor.

### CAPÍTULO 18. Banco de preguntas del tribunal

Genera al menos 60 preguntas y respuestas basadas en el proyecto real, organizadas por dificultad:

- Conceptos generales.
- Arquitectura.
- Django y ORM.
- Modelos y base de datos.
- Formularios y validaciones.
- Autenticación y permisos.
- Seguridad y privacidad.
- QR.
- Compras y puntos.
- Recompensas y canjes.
- Transacciones y concurrencia.
- Pruebas.
- Rendimiento.
- Despliegue.
- Decisiones de diseño.
- Limitaciones y futuras mejoras.

Las respuestas deben explicar el razonamiento y no limitarse a una frase.

Incluye preguntas difíciles como:
- ¿Qué impediría que un usuario se concediera puntos a sí mismo?
- ¿Qué ocurriría si dos empleados intentaran canjear simultáneamente la misma recompensa?
- ¿Cómo se evitarían dos asignaciones de puntos para la misma compra?
- ¿Qué pasa si falla el envío de un correo después de crear una cuenta?
- ¿Cómo se protege la información personal?
- ¿Qué sucede si una migración falla en producción?
- ¿Qué parte del sistema cambiarías si aumentara considerablemente el número de clientes?

Responde según el código real. Cuando un control no exista, explica honestamente el riesgo y la solución recomendada.

### CAPÍTULO 19. Glosario técnico

Define con lenguaje sencillo y ejemplos aplicados al proyecto términos como:

- Modelo.
- Vista.
- URL.
- Formulario.
- ORM.
- Migración.
- Middleware.
- Decorador.
- Servicio de negocio.
- Transacción.
- Clave foránea.
- Índice.
- Hash de contraseña.
- Token.
- CSRF.
- Idempotencia.
- Concurrencia.
- API REST.
- Entorno virtual.
- Variable de entorno.
- Contenedor.
- Proxy inverso.
- Backup.
- CI/CD.

Añade otros términos relevantes que aparezcan en el código.

### CAPÍTULO 20. Conclusiones y valoración técnica

Redacta unas conclusiones que expliquen:

- Qué se ha construido realmente.
- Qué necesidades satisface.
- Qué conocimientos técnicos demuestra.
- Qué decisiones han sido importantes.
- Qué limitaciones siguen presentes.
- Qué condiciones deberían cumplirse antes de producción.
- Qué posibilidades de evolución tiene.

Evita las afirmaciones grandilocuentes o no demostrables.

## 5. Requisitos para el código comentado

Quiero que la explicación del código sea un elemento central del documento.

No basta con insertar fragmentos de código sin contexto.

Cada fragmento debe estar acompañado de:

1. Ruta exacta del archivo.
2. Objetivo.
3. Explicación del flujo de ejecución.
4. Código real.
5. Código didáctico comentado, cuando resulte útil.
6. Explicación de los elementos importantes.
7. Relación con otros módulos.
8. Ejemplo práctico.
9. Consideraciones de seguridad o integridad.
10. Una explicación oral resumida.

Para los fragmentos más importantes, añade una tabla:

| Elemento | Función | Explicación aplicada al proyecto |
|---|---|---|
| Clase o función | Responsabilidad | Qué hace y por qué |
| Parámetro | Dato recibido | De dónde procede |
| Validación | Restricción | Qué evita |
| Operación de base de datos | Persistencia | Qué cambia |
| Retorno o respuesta | Resultado | Qué recibe el usuario |

No intentes reproducir literalmente todo el repositorio en un único documento. Prioriza los fragmentos relevantes y explica el resto mediante referencias precisas. Si una implementación extensa necesita más espacio, divídela en subsecciones.

## 6. Diagramas obligatorios

Incluye diagramas legibles, derivados del código real, para:

- Arquitectura general.
- Organización de módulos.
- Entidad-relación.
- Flujo de autenticación.
- Registro y verificación de email.
- Registro de compra y asignación de puntos.
- Solicitud y canje de recompensa.
- Roles y permisos.
- Despliegue, si está implementado o se presenta como propuesta.

Utiliza Mermaid si es compatible con el formato final. Comprueba que los diagramas sean sintácticamente válidos y que sus elementos correspondan a la aplicación real.

## 7. Requisitos de calidad y profundidad

El documento debe ser:

- Extenso y detallado.
- Pedagógico, sin perder precisión técnica.
- Adecuado para una defensa académica.
- Coherente entre capítulos.
- Basado en evidencia del repositorio.
- Fácil de consultar por índice y referencias.
- Comprensible para alguien que conoce programación, pero necesita explicar las decisiones y los flujos.
- Explícito sobre los límites de lo que se ha comprobado.

Evita explicaciones repetitivas. Puedes referenciar un concepto explicado anteriormente, pero no omitas la explicación cuando sea necesaria para comprender un módulo por separado.

Utiliza nombres reales de clases, métodos, modelos y rutas. Siempre que sea posible, indica las líneas aproximadas o el fragmento concreto donde se encuentra la implementación.

Si existe documentación anterior, reutiliza lo que siga siendo correcto y actualízalo conforme al código real.

## 8. Archivos de salida

Genera una carpeta nueva llamada:

`docs/defensa_proyecto/`

Dentro, crea como mínimo:

1. `01_memoria_tecnica_funcional.md`  
   Documento principal completo.

2. `02_guion_defensa_oral.md`  
   Guion de presentación, tiempos, orden de demostración y mensajes clave.

3. `03_preguntas_y_respuestas_tribunal.md`  
   Banco de preguntas y respuestas técnicas.

4. `04_mapa_codigo_y_funcionalidades.md`  
   Índice que relacione funcionalidades con rutas, clases, métodos, modelos y pruebas.

5. `05_limitaciones_y_pendientes.md`  
   Limitaciones, discrepancias, riesgos y mejoras propuestas.

6. `diagramas/`  
   Diagramas Mermaid en archivos independientes cuando resulte útil.

7. `README.md`  
   Índice general de la documentación, propósito de cada archivo y orden recomendado de lectura.

Si las herramientas disponibles permiten generar documentos Word de forma fiable, genera además un archivo DOCX de la memoria principal, con portada, índice, estilos de títulos, numeración de capítulos, tablas y bloques de código legibles. Si no es posible generar un DOCX correctamente, conserva los archivos Markdown y documenta la limitación.

No sobrescribas documentos existentes. Si ya existen archivos con los mismos nombres, crea una versión nueva o solicita confirmación.

## 9. Estrategia de ejecución

No intentes redactar todos los capítulos sin revisar previamente el código.

Trabaja en estas etapas:

**Etapa A — Inventario**
- Inspecciona el repositorio.
- Construye un mapa de módulos, modelos, rutas, servicios, plantillas y pruebas.
- Identifica qué documentación existente puede reutilizarse.

**Etapa B — Verificación**
- Contrasta las funcionalidades con el código.
- Ejecuta comprobaciones seguras cuando sea posible.
- Registra evidencias, dudas y discrepancias.

**Etapa C — Documentación**
- Redacta los capítulos por módulos.
- Comenta el código relevante.
- Genera los diagramas.
- Construye el guion de defensa y el banco de preguntas.

**Etapa D — Revisión de consistencia**
- Comprueba que las rutas y los nombres de clases existen.
- Comprueba que los ejemplos de código corresponden al repositorio.
- Comprueba que los diagramas coinciden con la arquitectura.
- Elimina afirmaciones no verificadas.
- Detecta contradicciones entre capítulos.
- Comprueba que los documentos están completos y se enlazan correctamente.

**Etapa E — Entrega**
- Presenta un resumen de los archivos generados.
- Indica las partes del repositorio analizadas.
- Enumera las comprobaciones realizadas y sus resultados reales.
- Señala las partes que no pudieron verificarse.
- Resume las principales limitaciones detectadas.
- Propón un orden de estudio para preparar la defensa.

## 10. Condiciones finales

La prioridad es la exactitud y la comprensión profunda del proyecto, no la velocidad de generación.

No modifiques la aplicación durante esta tarea.

No inventes resultados.

No ocultes defectos.

No presentes funcionalidades planificadas como implementadas.

No sustituyas el análisis del código por teoría genérica.

Quiero terminar con una documentación que me permita explicar de manera convincente qué hace Caneca Furada, cómo está construida, cómo funciona internamente, qué decisiones técnicas se han tomado, cómo se ha comprobado y qué aspectos quedan por mejorar.

Comienza ahora con la inspección del repositorio y continúa hasta generar los documentos solicitados, respetando las etapas y todas las restricciones anteriores.
# PROMPT MAESTRO — PLATAFORMA PERSONAL ADAPTATIVA DE CIBERSEGURIDAD, PENTESTING Y CYBER RANGE

> **Estado:** Documento maestro / fuente de verdad para la IA de desarrollo  
> **Objetivo:** Construir una plataforma personal de aprendizaje técnico de ciberseguridad que pueda crecer durante años, desde fundamentos hasta investigación avanzada.  
> **Principio central:** La plataforma debe enseñar a pensar, investigar, conectar conceptos, practicar y retener; no solo a memorizar comandos ni completar cursos.

---

# 0. INSTRUCCIÓN PRINCIPAL PARA LA IA DE DESARROLLO

Quiero que diseñes y construyas una aplicación web completa de aprendizaje técnico de ciberseguridad, pentesting, red team, blue team, investigación de vulnerabilidades y fundamentos.

La plataforma debe estar diseñada inicialmente para **un único usuario (OWNER)** y funcionar como mi entorno personal permanente de:

- aprendizaje;
- práctica;
- documentación;
- evaluación;
- laboratorios;
- repetición espaciada;
- retos;
- CTF;
- análisis;
- investigación;
- seguimiento de progreso;
- memorización a largo plazo;
- entrenamiento de metodología profesional.

No debe ser una simple colección de cursos.

Debe comportarse como una combinación de:

- academia técnica;
- instructor adaptativo;
- cyber range;
- laboratorio de pentesting;
- sistema de evaluación;
- knowledge base;
- gestor de notas;
- sistema de repetición espaciada;
- plataforma CTF;
- biblioteca de vulnerabilidades;
- cheatsheet interactivo;
- simulador de escenarios;
- historial técnico de aprendizaje;
- motor de retención;
- sistema de concentración;
- tutor socrático;
- sistema de detección de conocimiento fragmentado.

Debe poder utilizarla una persona que empieza literalmente desde cero y también alguien con experiencia avanzada.

Las características pedagógicas descritas en este documento son **parte del núcleo del producto**. No deben eliminarse posteriormente como “extras” para simplificar la plataforma.

---

# 1. PRINCIPIO FUNDAMENTAL

La plataforma debe enseñar a **pensar como profesional de seguridad**, no a memorizar recetas.

Evitar el modelo:

```text
Nmap detecta puerto
→ buscar exploit
→ ejecutar exploit
```

Favorecer:

```text
Reconocimiento
↓
Enumeración
↓
Comprensión de superficie de ataque
↓
Observación
↓
Hipótesis
↓
Validación
↓
Identificación de vulnerabilidad
↓
Explotación controlada
↓
Post-explotación
↓
Escalada
↓
Movimiento/pivoting cuando corresponda
↓
Evidencia
↓
Impacto
↓
Remediación
↓
Documentación
```

Los laboratorios deben premiar metodología correcta aunque existan caminos alternativos.

La pregunta más importante no debe ser:

> ¿Llegó a root?

Debe ser:

> ¿Entendió qué estaba ocurriendo, formuló hipótesis razonables, validó evidencia y puede explicar el ataque y su causa raíz?

---

# 2. PRINCIPIOS PEDAGÓGICOS OBLIGATORIOS

Crear desde el inicio:

```text
PEDAGOGICAL_PRINCIPLES.md
```

Debe definir y proteger como principios permanentes:

- Retrieval Practice
- Active Recall
- Spaced Repetition
- Interleaving
- Adaptive Difficulty
- Transfer Learning
- Error-Based Learning
- Knowledge Integration
- Knowledge Fragmentation Detection
- Progressive Disclosure
- Socratic Guidance
- Attention-Friendly UX
- First-Principles Learning
- Learn → Use
- Deliberate Practice
- Confidence Calibration
- Long-Term Retention
- No-Shame Design

La plataforma no debe optimizarse para:

```text
terminar cursos
acumular XP
ver videos
aprobar una prueba una vez
```

Debe optimizarse para:

```text
comprender
recordar
relacionar
aplicar
investigar
resolver problemas nuevos
explicar por qué funciona algo
trabajar de manera autónoma
```

---

# 3. RESTRICCIÓN DE SEGURIDAD

Todo contenido ofensivo debe estar diseñado exclusivamente para:

- laboratorios locales;
- Docker;
- máquinas virtuales;
- redes privadas;
- entornos deliberadamente vulnerables;
- CTF;
- hosts expresamente marcados como propiedad del usuario;
- objetivos con autorización explícita.

Nunca asumir autorización sobre infraestructura externa.

No implementar funciones que ataquen automáticamente Internet ni servicios de terceros.

Separar claramente:

```text
PLATFORM NETWORK
≠
LAB NETWORK
```

Nunca ejecutar servicios vulnerables directamente dentro del backend principal de la plataforma.

---

# 4. VULNERABILIDADES CONOCIDAS Y DESCONOCIDAS

La plataforma puede cubrir exhaustivamente:

- CVE;
- CWE;
- OWASP;
- MITRE ATT&CK;
- CISA KEV;
- errores de configuración;
- vulnerabilidades web;
- APIs;
- autenticación;
- autorización;
- criptografía;
- redes;
- Linux;
- Windows;
- Active Directory;
- cloud;
- contenedores;
- Kubernetes;
- mobile;
- hardware/IoT;
- reversing;
- binary exploitation;
- malware;
- supply chain;
- etc.

## 4.1 NO usar zero-days secretos reales

No diseñar la plataforma alrededor de vulnerabilidades secretas/no públicas reales.

En su lugar crear:

## Synthetic Unknown Vulnerabilities

Laboratorios con vulnerabilidades originales construidas específicamente para la plataforma.

Deben:

- no tener walkthrough público;
- no indicar su categoría;
- no indicar la herramienta correcta;
- poder combinar varios errores;
- imitar condiciones reales;
- permitir white-box o black-box;
- requerir observación;
- permitir debugging;
- permitir análisis de protocolos;
- permitir reversing;
- exigir formulación de hipótesis.

Ejemplo:

```text
Servicio TCP custom
↓
protocolo poco documentado
↓
parser con comportamiento inesperado
↓
usuario captura tráfico
↓
formula hipótesis
↓
reproduce el fallo
↓
construye PoC dentro del laboratorio
↓
documenta root cause
↓
propone corrección
```

---

# 5. MODELO PEDAGÓGICO ADAPTATIVO

Cada concepto debe tener un nivel estimado:

```text
0 — desconocido
1 — reconocimiento
2 — comprensión básica
3 — aplicación guiada
4 — aplicación autónoma
5 — integración con otros conceptos
6 — resolución de problemas nuevos
7 — dominio avanzado
```

Registrar por separado:

- conocimiento teórico;
- habilidad práctica;
- retención;
- autonomía;
- velocidad;
- dependencia de pistas;
- número de intentos;
- errores recurrentes;
- confianza declarada;
- confianza real;
- transferencia a contextos nuevos;
- conexión conceptual;
- metodología;
- capacidad de explicar desde primeros principios.

---

# 6. AJUSTE AUTOMÁTICO DE DIFICULTAD

Si el usuario:

- responde correctamente con frecuencia;
- resuelve laboratorios sin pistas;
- explica correctamente por qué funciona algo;
- aplica conceptos en escenarios nuevos;

aumentar dificultad gradualmente.

Si acumula errores:

- reducir dificultad;
- regresar al fundamento;
- dividir el problema;
- generar microlección;
- explicar desde otro ángulo;
- introducir analogías;
- usar diagrama;
- usar terminal;
- usar paquetes;
- usar ejemplo práctico.

Nunca convertir una mala racha en una barrera.

Buscar siempre:

```text
capacidad actual + pequeño reto
```

Evitar:

```text
demasiado fácil → aburrimiento
demasiado difícil → frustración
```

---

# 7. GRAFO DE PREREQUISITOS

Cada conocimiento debe modelarse como nodo.

Ejemplo:

```text
IPv4
 ↓
Subnetting
 ↓
Routing
 ↓
ARP
 ↓
TCP
 ↓
Nmap
 ↓
Enumeración
 ↓
Pivoting
```

Otro:

```text
HTTP
 ↓
Cookies
 ↓
Sessions
 ↓
Authentication
 ↓
Authorization
 ↓
IDOR
```

Otro:

```text
Linux Permissions
 ↓
SUID
 ↓
sudo
 ↓
cron
 ↓
Privilege Escalation
```

Los prerequisitos **NO bloquean** contenido.

Solo recomendar:

```text
Recomendado antes de este reto:

✓ HTTP
✓ Cookies
✓ SQL básico
△ Enumeración web
✕ Burp Repeater

[Intentar de todas formas]
```

---

# 8. KNOWLEDGE GRAPH

Crear grafo navegable.

Ejemplo al abrir `ARP`:

```text
Prerequisitos:
← IPv4
← Ethernet
← MAC

Relacionado:
↔ DHCP
↔ Gateway
↔ Routing

Continúa con:
→ ARP Spoofing
→ MITM
→ Packet Analysis
```

Permitir visualizar conexiones gráficamente.

---

# 9. PROBLEMA CENTRAL: CONOCIMIENTO FRAGMENTADO

La plataforma debe detectar el caso:

```text
conocimiento individual alto
+
conexión conceptual baja
```

Ejemplo:

```text
ARP:      82%
DNS:      84%
Routing:  80%
TCP:      86%

Integrated Networking Scenario:
48%
```

Resultado:

```text
Fragmentation detected
```

Debe generar ejercicios integradores.

No basta preguntar:

> ¿Qué es ARP?

También:

```text
PC:
192.168.10.20/24
Gateway:
192.168.10.1

Destino:
8.8.8.8

¿Qué dirección resolverá mediante ARP y por qué?
```

---

# 10. MÉTRICA KNOWLEDGE FRAGMENTATION

Crear:

```text
Fragmentation Score
```

Debe comparar:

- conocimiento individual;
- rendimiento integrado;
- transferencia;
- errores de asociación;
- explicación de cadenas completas.

Debe aparecer en dashboard.

Ejemplo:

```text
TCP:       84%
ARP:       78%
Routing:   76%

Integrated Networking:
48%

Knowledge Fragmentation: HIGH
```

El motor debe recomendar ejercicios de integración.

---

# 11. CONCEPT CONNECTIVITY SCORE

Crear métrica:

```text
Concept Connectivity
```

Evaluar si el usuario puede relacionar:

```text
DNS
ARP
Gateway
Routing
TCP
TLS
HTTP
```

No confundir mastery individual con mastery integrado.

---

# 12. RETRIEVAL PRACTICE PERMANENTE

No limitar repaso a volver a leer.

Flujo:

```text
Pregunta
↓
Intento del usuario
↓
Evaluación
↓
Explicación
↓
Nueva variante
```

El sistema debe pedir recuperar conocimiento antes de mostrar respuesta.

---

# 13. TEST RÁPIDO BAJO DEMANDA

Botón persistente:

```text
Repasar ahora
```

Opciones:

```text
5 preguntas
10 preguntas
15 preguntas
20 preguntas
```

o:

```text
5 minutos
10 minutos
20 minutos
```

El sistema genera test automáticamente.

---

# 14. BOTÓN “TEST ALEATORIO”

Botón persistente:

```text
🎲 Test aleatorio
```

Opciones:

```text
Todos mis conocimientos
Solo fundamentos
Solo debilidades
Solo olvidados
Solo networking
Solo web
Solo Linux
Solo AD
Nivel adaptativo
```

Las preguntas deben cambiar de contexto para impedir memorizar respuestas.

---

# 15. MODOS DE REPASO

Implementar:

## Repaso general
Preguntas de cualquier conocimiento anterior.

## Repaso de debilidades
Prioriza rendimiento bajo.

## Repaso olvidado
Prioriza riesgo de olvido.

## Repaso por tema
Ejemplo `Networking`.

## Repaso mixto
Mezcla dominios.

## Repaso sorpresa
La plataforma selecciona.

## Repaso antes de laboratorio
Evalúa prerequisitos del lab.

## Repaso de errores personales
Usa ErrorPattern.

## Repaso de integración
Combina conceptos relacionados.

---

# 16. PREGUNTAS ALEATORIAS Y VARIANTES

No almacenar una sola pregunta por concepto.

Cada concepto debe tener:

```text
plantillas
variantes
contextos
dificultades
representaciones
```

Ejemplo TCP:

```text
Ordena SYN / ACK / SYN-ACK.
```

```text
Interpreta esta captura.
```

```text
¿Por qué existe el handshake?
```

```text
Nmap envió SYN y recibió RST. ¿Qué puedes inferir?
```

```text
Analiza este PCAP.
```

---

# 17. GENERADOR DE PREGUNTAS CON IA

La IA puede crear preguntas nuevas.

Pero debe registrar:

```text
concepto
dificultad
respuesta esperada
criterios de evaluación
prerequisitos
tipo de pregunta
```

No generar preguntas desconectadas del knowledge graph.

---

# 18. INTERLEAVING

No hacer siempre:

```text
20 preguntas ARP
20 preguntas DNS
20 preguntas TCP
```

También:

```text
ARP
TCP
Linux
DNS
HTTP
Routing
ARP
HTTP
```

Obligar al usuario a identificar qué conocimiento aplicar.

---

# 19. FORGETTING ENGINE

Cada concepto debe registrar:

```text
last_seen
last_tested
last_correct
last_failed
difficulty
retention_score
retrieval_strength
forgetting_risk
```

Ejemplo:

```text
ARP

Comprensión:        82%
Práctica:           75%
Último test:        37 días
Retención estimada: 52%

Estado:
REPASAR
```

---

# 20. RETENTION SCORE

No calcular solo por tiempo.

Considerar:

- tiempo desde última práctica;
- respuestas correctas;
- dificultad;
- calidad de explicación;
- pistas;
- errores recientes;
- aplicación práctica;
- transferencia;
- confianza.

Estados:

```text
Aprendido
Consolidando
Dominado
Necesita repaso
Retención degradada
```

Nunca usar “completado para siempre”.

---

# 21. REPETICIÓN ESPACIADA

Puntos iniciales:

```text
día 0
día 1
día 3
día 7
día 14
día 30
día 90
día 180
día 365
```

Adaptar según rendimiento.

No repetir la misma pregunta.

Ejemplo:

Primero:

```text
¿Qué hace ARP?
```

Después:

```text
Tu máquina necesita acceder a 8.8.8.8.
¿Qué IP intentará resolver por ARP?
```

Luego PCAP.

Luego escenario ofensivo/defensivo.

---

# 22. DAILY REVIEW

Dashboard:

```text
Repaso recomendado hoy
5 preguntas
~4 minutos
```

Debe ser pequeño para favorecer constancia.

---

# 23. DAILY QUESTION

Opcional:

```text
Pregunta del día
```

Debe tomar menos de dos minutos.

No convertirla en obligación ni castigar por omitirla.

---

# 24. WEEKLY CHECKPOINT

Una vez por semana sugerir:

```text
Checkpoint semanal
```

Combinar:

- teoría;
- razonamiento;
- outputs;
- mini-lab;
- integración.

---

# 25. MONTHLY RETENTION REVIEW

Una vez al mes:

```text
Fuertes
Estables
En riesgo
Olvidados
```

Generar plan de repaso.

---

# 26. LONG-TERM RETENTION REPORT

Mostrar retención a:

```text
30 días
90 días
180 días
365 días
```

Esta métrica es más importante que porcentaje de curso completado.

---

# 27. COLD CASE

Implementar modo:

```text
Cold Case
```

Seleccionar laboratorio ya resuelto meses atrás y generar una nueva variante.

Cambiar:

- IP;
- puertos;
- rutas;
- usuarios;
- nombres;
- servicios secundarios;
- credenciales;
- flags;
- topología;
- vulnerabilidad secundaria.

Objetivo:

distinguir:

```text
aprendí el concepto
```

de:

```text
recuerdo el walkthrough
```

---

# 28. TRANSFER TEST

Aplicar conocimiento en contexto diferente.

Ejemplo:

Aprendió IDOR mediante:

```text
/invoice?id=101
```

Evaluar después con:

```text
/api/patients/UUID
```

o GraphQL, app móvil, API JSON, etc.

Si solo resuelve el ejemplo original, no considerar dominio real.

---

# 29. CONFIDENCE CALIBRATION

Antes de determinadas respuestas:

```text
¿Qué tan seguro estás?

Nada seguro
Poco seguro
Seguro
Muy seguro
```

Comparar:

```text
confianza declarada
vs
resultado real
```

Especial atención:

```text
Alta confianza + respuesta incorrecta
```

Debe generar repaso, porque puede representar conocimiento incorrecto muy consolidado.

---

# 30. ERROR PATTERN ENGINE

Registrar errores personales:

```text
Concepto:
ARP

Error:
Confundir ARP con TCP handshake.

Fecha:
...

Repeticiones:
3
```

Generar ejercicios diseñados para romper asociaciones incorrectas.

---

# 31. ERROR MEMORY

Dashboard:

```text
Errores que todavía repites
```

Ejemplo:

```text
ARP ↔ TCP
Authentication ↔ Authorization
SSH anonymous ↔ FTP anonymous
Network address ↔ first usable host
```

No usar para avergonzar.

Usar para dirigir práctica.

---

# 32. FAILED ATTEMPTS

Guardar intentos fallidos.

Ejemplo:

```text
Intenté anonymous SSH.
Resultado: no corresponde.

Concepto relacionado:
Anonymous authentication es común en FTP.
```

Permitir convertir un fallo en tarjeta de repaso.

---

# 33. MÉTRICAS PEDAGÓGICAS PRINCIPALES

Registrar por usuario y dominio:

```text
Knowledge Score
Practical Skill
Retention
Autonomy
Concept Connectivity
Knowledge Fragmentation
Problem Solving
Methodology
Hint Dependency
Transfer Ability
Confidence Calibration
First Principles Score
Independence Score
```

---

# 34. INDEPENDENCE SCORE

Medir capacidad de resolver sin:

- hint;
- walkthrough;
- solución;
- búsqueda específica de respuesta.

Ejemplo:

```text
Independence Score: 68%
```

---

# 35. FIRST PRINCIPLES SCORE

Medir si puede explicar:

```text
por qué funciona
```

y no solo:

```text
qué comando ejecutar
```

---

# 36. TRANSFER SCORE

Medir capacidad de aplicar conocimientos en escenarios nuevos.

---

# 37. METHODOLOGY SCORE

Evaluar:

- enumeración;
- observación;
- hipótesis;
- validación;
- disciplina;
- evidencia;
- razonamiento;
- limpieza;
- reporting.

No premiar únicamente obtener shell/root.

---

# 38. HINT DEPENDENCY

Ejemplo:

```text
Labs completados: 42

Sin hints: 21
Hint 1:    12
Hint 2:     6
Solución:   3
```

Mostrar evolución mensual.

---

# 39. ATTENTION-FRIENDLY DESIGN

Diseñar para minimizar fricción cognitiva.

No diagnosticar ninguna condición médica.

Debe servir bien para usuarios con:

- dificultad para iniciar;
- distracción;
- fatiga;
- hiperfoco;
- problemas de memoria;
- sobrecarga de información.

Principio:

```text
La plataforma debe adaptarse al usuario,
no exigir que el usuario se adapte a la plataforma.
```

---

# 40. QUICK START

Al abrir la plataforma NO mostrar demasiadas decisiones.

Mostrar principalmente:

```text
Continuar
```

Ejemplo:

```text
NET-01.4
Packet Analysis

Duración sugerida:
15 minutos

[Continuar]
```

Secundario:

```text
Repasar
Explorar
Retos
```

---

# 41. BOTÓN “NO SÉ QUÉ ESTUDIAR”

Debe existir permanentemente:

```text
No sé qué estudiar
```

El motor debe analizar:

- repasos vencidos;
- forgetting risk;
- conceptos débiles;
- fragmentación;
- errores recurrentes;
- prerequisitos;
- tiempo disponible;
- dificultad actual;
- nivel de concentración declarado;
- laboratorio reciente;
- objetivos del roadmap.

Y devolver **una sola actividad recomendada**, no diez opciones.

Ejemplo:

```text
Tienes 15 minutos.

Hoy te recomiendo:
NET-02 — ARP y Gateway

Razón:
ARP tiene retención baja y está afectando Routing.

[Empezar]
```

Este botón es un mecanismo para reducir fricción de inicio.

---

# 42. REGLA DE LOS 5 MINUTOS

Modo:

```text
Solo 5 minutos
```

Seleccionar automáticamente:

```text
1 concepto
2 preguntas
1 microejercicio
```

Al final:

```text
Terminaste.

¿Quieres continuar?
```

No obligar.

---

# 43. FOCUS MODE

Modo:

```text
Focus Mode
```

Ocultar:

- estadísticas secundarias;
- achievements;
- notificaciones;
- contenido no necesario;
- navegación distractora.

Mostrar:

```text
objetivo actual
contenido
terminal/lab
notas
timer
```

---

# 44. SESSION GOAL

Toda sesión debe comenzar con un objetivo pequeño y concreto.

Ejemplo:

```text
Hoy solo necesitas comprender:

Por qué una máquina remota utiliza la MAC del gateway.
```

---

# 45. MICRO-OBJETIVOS

Ejemplo:

```text
- [ ] identificar red local
- [ ] identificar gateway
- [ ] observar ARP
- [ ] observar DNS
- [ ] observar TCP handshake
```

Mostrar progreso inmediato.

---

# 46. TIMER / POMODORO

Implementar temporizador configurable.

Presets:

```text
15 / 5
25 / 5
40 / 10
50 / 10
```

Permitir personalizado.

No imponer Pomodoro.

Algunas personas alcanzan concentración justo cuando termina un bloque fijo.

---

# 47. MODOS DE TIMER

Permitir:

```text
Count Up
Pomodoro
Countdown
No Timer
```

**Count Up es obligatorio** porque un temporizador descendente puede generar presión.

---

# 48. FOCUS SESSION

Registrar opcionalmente:

```text
inicio
fin
tiempo activo
tema
actividad
laboratorio
interrupciones declaradas
```

No convertirlo en vigilancia.

---

# 49. BREAK REMINDERS

Después de periodos largos:

```text
Llevas 52 minutos concentrado.

¿Quieres hacer una pausa de 5 minutos?
```

Opciones:

```text
Pausa
Seguir
No volver a preguntar hoy
```

---

# 50. HYPERFOCUS PROTECTION

Configurable:

```text
Maximum Focus Reminder:
90 minutos
```

Nunca detener automáticamente.

Solo recordar:

```text
Has trabajado 90 minutos.

Guarda notas.
Haz una pausa si la necesitas.
Decide conscientemente si continúas.
```

---

# 51. SESSION RESUME

Guardar:

- lección;
- posición;
- notas;
- último ejercicio;
- laboratorio;
- estado seguro de terminal si es posible.

Al volver:

```text
Continuar exactamente donde estabas
```

---

# 52. CONTEXT RECAP

Si han pasado varios días:

```text
Última vez aprendiste:

• ARP
• Gateway
• DNS

Antes de continuar:
3 preguntas rápidas
```

Si responde bien, continuar.

Si falla, microrepaso.

---

# 53. NO INFORMATION DUMPING

Usar Progressive Disclosure.

Preferir:

```text
Concepto
↓
Ejemplo
↓
Pregunta
↓
detalle adicional
```

No:

```text
40 minutos de teoría
↓
test
```

---

# 54. LEARN → USE

Después de cada concepto importante debe existir una acción.

Ejemplo:

```text
Aprender ARP
↓
ver ip neigh
↓
provocar ARP
↓
observar Wireshark
```

---

# 55. REGLAS MENTALES

Cada tema debe tener:

```text
🧠 Regla mental
```

Ejemplos:

```text
IP = dónde quiero llegar.
MAC = a quién se lo entrego ahora.
Puerto = qué servicio quiero.
```

```text
TCP crea la conexión.
TLS la protege.
HTTP lleva la conversación web.
```

Estas reglas deben reaparecer en repasos.

---

# 56. MEMORY HOOKS

Permitir:

- analogía;
- regla corta;
- diagrama;
- error típico;
- ejemplo ofensivo;
- ejemplo defensivo;
- packet capture;
- terminal;
- código.

El sistema debe aprender qué formato funciona mejor para cada usuario.

---

# 57. EXPLANATION PREFERENCE

Registrar:

```text
texto
diagrama
ejemplo
terminal
analogía
packet capture
código
```

Adaptar explicaciones futuras.

---

# 58. PROGRESSIVE DIFFICULTY

Ejemplo DNS:

Nivel 1:
```text
¿Qué significa DNS?
```

Nivel 2:
```text
¿Qué IP consulta tu máquina?
```

Nivel 3:
```text
Analiza dig.
```

Nivel 4:
```text
Analiza PCAP.
```

Nivel 5:
```text
Diagnostica fallo.
```

Nivel 6:
```text
Investiga comportamiento DNS extraño.
```

---

# 59. FRUSTRATION DETECTION

Si ocurren:

- muchos errores consecutivos;
- múltiples hints;
- reinicios;
- tiempo anormalmente alto;
- acciones repetidas;

no aumentar dificultad.

Mostrar algo neutral:

```text
Parece que falta una pieza anterior.
Vamos a reconstruirla.
```

Generar microlección.

---

# 60. NO-SHAME DESIGN

Nunca mostrar:

```text
Perdiste tu racha.
Fallaste otra vez.
Vas atrasado.
```

Preferir:

```text
Este concepto necesita refuerzo.
```

Gamificación sin presión innecesaria.

---

# 61. ACCESSIBILITY

Ofrecer:

- reduced motion;
- distraction-free;
- tamaño de fuente;
- line spacing;
- high contrast;
- simplified layout;
- reduced visual noise;
- dark/light mode.

---

# 62. TIPOS DE SESIÓN

Permitir:

```text
5 min  — Micro Review
15 min — Quick Learn
25 min — Focus
45 min — Deep Practice
90 min — Lab
Libre  — Explore
```

---

# 63. ESTRUCTURA PRINCIPAL DE NAVEGACIÓN

Sidebar izquierdo en desktop.

Drawer o menú inferior en móvil.

Categorías:

```text
Dashboard

Fundamentos
  Redes
  Linux
  Windows
  Programación
  Web
  Criptografía
  Bases de datos
  Arquitectura de computadores

Pentesting
  Metodología
  Reconocimiento
  Enumeración
  Explotación
  Privilege Escalation
  Pivoting
  Post-exploitation
  Reporting

Web Security
  HTTP
  Authentication
  Authorization
  SQLi
  XSS
  CSRF
  SSRF
  SSTI
  XXE
  File Upload
  Path Traversal
  Command Injection
  Deserialization
  JWT
  OAuth
  APIs
  GraphQL
  WebSockets
  Business Logic
  Race Conditions

Linux
Windows
Active Directory
Networking
Wi-Fi
Cloud
Containers
Kubernetes
Mobile
Reverse Engineering
Binary Exploitation
Malware Analysis
OSINT
Threat Intelligence
Blue Team
Detection Engineering
Digital Forensics
Red Team
Social Engineering
Hardware / IoT
Criptografía

Retos
Laboratorios
Evaluaciones
Vulnerabilidades
Herramientas
Cheatsheets
Notas
Historial
Roadmap
Configuración
```

---

# 64. ESTRUCTURA DE CADA LECCIÓN

Cada tema debe incluir cuando corresponda:

## Concepto
Desde fundamentos.

## Cómo funciona internamente
No solo definición.

## Por qué importa en seguridad

## Visualización

## Ejemplo

## Comandos
Solo después de explicar el mecanismo.

## Errores frecuentes

## Error personal
Si aplica.

## 🧠 Regla mental

## Perspectiva ofensiva

## Perspectiva defensiva

## Mini evaluación

## Laboratorio

## Repaso

## Relaciones
Con wikilinks/knowledge graph.

---

# 65. SISTEMA DE NOTAS

REQUISITO IMPORTANTE.

### Desktop

```text
┌───────────┬────────────────────┬──────────────┐
│ Sidebar   │ Contenido          │ Notas        │
│           │                    │ Markdown     │
└───────────┴────────────────────┴──────────────┘
```

### Mobile

Notas debajo del contenido.

Características:

- Markdown;
- preview;
- autosave;
- notas por lección;
- notas globales;
- tags;
- búsqueda;
- backlinks;
- wikilinks;
- exportación a Obsidian.

Ejemplo:

```text
[[ARP]]
[[DNS]]
[[Privilege Escalation]]
```

---

# 66. OBSIDIAN COMPATIBILITY

Exportación:

```markdown
---
id: NET-01
tags:
  - networking
  - fundamentals
---

# ARP

Relacionado:

[[IPv4]]
[[MAC Address]]
[[Routing]]
[[Gateway]]

## Regla mental

IP = dónde quiero llegar.
MAC = a quién se lo entrego ahora.
```

---

# 67. BÚSQUEDA GLOBAL

Buscar en:

- conceptos;
- notas;
- cheatsheets;
- labs;
- vulnerabilidades;
- comandos;
- resultados anteriores;
- errores personales.

---

# 68. COMMAND PALETTE

Atajo:

```text
Ctrl+K
```

Ejemplos:

```text
Open ARP
Start review
Create note
Find Nmap cheat sheet
Resume last lab
```

---

# 69. EVALUACIONES

Tipos:

- opción múltiple;
- verdadero/falso;
- explicación libre;
- completar comando;
- identificar error;
- interpretar output;
- analizar PCAP;
- analizar HTTP;
- analizar logs;
- analizar código;
- debugging;
- troubleshooting;
- investigación abierta;
- laboratorio.

Evitar que la mayoría sean multiple-choice.

---

# 70. EVALUACIÓN BASADA EN RAZONAMIENTO

Ejemplo:

```text
Host: 10.10.10.50

22 open
80 open
3306 open
```

Preguntar:

```text
¿Qué harías ahora?
¿Por qué?
¿Qué hipótesis tienes?
¿Qué evidencia necesitas?
```

Evaluar metodología.

---

# 71. SCENARIO RANDOMIZER

Generar escenarios con valores aleatorios.

Ejemplo:

```text
IP:
10.20.30.25/27

Gateway:
10.20.30.1

Target:
10.20.30.60
```

Preguntar:

```text
¿Local o remoto?
¿Qué MAC necesitas?
```

Guardar variantes para no repetir innecesariamente.

---

# 72. EXAM GENERATOR

Permitir:

```text
Crear examen
```

Configurar:

- temas;
- duración;
- dificultad;
- cantidad;
- incluir labs;
- sin pistas.

---

# 73. MODO EXAMEN

Desactivar:

- notas;
- hints;
- cheatsheets;
- respuestas anteriores.

Registrar:

- duración;
- comandos;
- errores;
- resultado;
- metodología.

Luego generar análisis pedagógico.

---

# 74. DASHBOARD

Mostrar:

## Nivel global

## Nivel por dominio

Ejemplo:

```text
Networking           ███████░░░ 72%
Linux                ████████░░ 84%
Windows              █████░░░░░ 51%
Web                  ███████░░░ 73%
Active Directory     ████░░░░░░ 42%
Scripting            ███████░░░ 76%
```

## Retención

## Fragmentación

## Concept Connectivity

## Conceptos débiles

## Conceptos olvidados

## Errores recurrentes

## Repasos pendientes

## Laboratorios recomendados

## Últimos avances

## Tiempo de práctica

## Pistas usadas

## Retos

## Independence Score

## Transfer Score

## Methodology Score

No saturar visualmente.

---

# 75. LEARNING HEALTH DASHBOARD

Mostrar resumido:

```text
Aprendizaje reciente
Retención
Autonomía
Fragmentación
Debilidades
Repasos pendientes
```

---

# 76. PERSONAL LEARNING MODEL

Mantener:

```text
preferred_session_length
preferred_explanation_type
average_focus_time
difficulty_tolerance
hint_dependency
memory_decay_pattern
best_learning_hours si el usuario decide registrarlo
```

No diagnosticar condiciones médicas.

---

# 77. CHEATSHEETS

Biblioteca:

- Nmap;
- ffuf;
- Gobuster;
- Burp;
- curl;
- netcat;
- socat;
- Wireshark;
- tcpdump;
- Linux;
- PowerShell;
- SMB;
- LDAP;
- Kerberos;
- Impacket;
- BloodHound;
- SQLmap;
- Hashcat;
- John;
- Metasploit;
- Docker;
- Git.

Cada comando:

```text
comando
qué hace
cuándo usarlo
por qué funciona
riesgo
ejemplo
error frecuente
alternativas
```

No limitar a listas.

---

# 78. BOTÓN “¿POR QUÉ?”

En comandos y técnicas:

```text
¿Por qué funciona?
```

Debe explicar mecanismo subyacente.

---

# 79. BOTÓN “VER EN PAQUETES”

Cuando aplique:

```text
Ver ejemplo Wireshark
```

---

# 80. BOTÓN “VER CÓDIGO”

Mostrar implementación mínima del concepto.

---

# 81. BOTÓN “EXPLÍCALO DE OTRA FORMA”

Puede usar:

- analogía;
- diagrama;
- código;
- paquete;
- terminal;
- mini ejercicio.

---

# 82. BASE DE VULNERABILIDADES

Ficha:

```text
Nombre
Categoría
CWE
CVE si existe
CVSS
Tecnologías afectadas
Prerequisitos
Fundamento
Causa raíz
Condición necesaria
Cómo identificarla
Cómo confirmarla
Impacto
Explotación en laboratorio
Mitigación
Detección
Variantes
Casos reales
Labs relacionados
Preguntas
```

---

# 83. ATTACK CHAINS

No almacenar solo vulnerabilidades aisladas.

Ejemplo:

```text
Initial Recon
↓
Web Enumeration
↓
Directory Discovery
↓
Hidden Admin Panel
↓
Authentication Bypass
↓
File Upload
↓
RCE
↓
www-data
↓
SUID Misconfiguration
↓
root
```

Relacionar conocimientos por paso.

---

# 84. ATTACK PATH VISUALIZER

Después del lab:

```text
External
 ↓
Web Enumeration
 ↓
SQLi
 ↓
Credential Extraction
 ↓
SSH
 ↓
Linux Host
 ↓
sudo misconfiguration
 ↓
root
```

---

# 85. METODOLOGÍA PENTEST PERMANENTE

Checklist:

```text
Scope
Recon
Host Discovery
Port Discovery
Service Enumeration
Application Enumeration
Credential Discovery
Vulnerability Analysis
Exploitation
Post-exploitation
Privilege Escalation
Pivoting
Evidence
Cleanup
Reporting
Remediation
```

---

# 86. NOTEBOOK DE PENTEST

Markdown:

```text
Target:
IP:
Hostname:

Ports:
Services:

Hypotheses:

Credentials:

Interesting files:

Potential vulnerabilities:

Failed attempts:

Next actions:

Evidence:
```

---

# 87. LAB REPORTING

Después de retos importantes:

```text
Executive summary
Attack path
Evidence
Root cause
Impact
Severity
Remediation
```

Evaluar calidad profesional.

---

# 88. REPORT QUALITY

Puntuar:

- claridad;
- evidencia;
- reproducibilidad;
- impacto;
- root cause;
- remediación.

---

# 89. TIPOS DE LABORATORIO

## Micro Labs
5–15 min, un concepto.

## Guided Labs
Con orientación.

## Semi-guided
Solo objetivos.

## Black Box
Solo IP/URL.

## Multi-stage
Cadena.

## Network Labs
Varias máquinas.

## Enterprise Labs
AD/red segmentada.

## Mystery Labs
No indicar vulnerabilidad.

## Research Labs
Código/protocolo/binario.

---

# 90. PRINCIPIO DE LABS NO OBVIOS

No decir:

```text
Este firewall bloquea SYN.
Usa X para evadirlo.
```

Mejor:

```text
Objetivo: enumerar el host.

Usuario prueba normal.
↓
Resultados inconsistentes.
↓
Analiza ICMP/TCP/timeouts.
↓
Formula:
“Puede existir filtrado.”
↓
Explora técnicas alternativas.
```

La plataforma debe enseñar el camino mental hacia la técnica.

---

# 91. PISTAS PROGRESIVAS

3–6 niveles.

## Hint 1
Pregunta orientadora.

## Hint 2
Concepto.

## Hint 3
Categoría de herramienta.

## Hint 4
Herramienta.

## Hint 5
Sintaxis parcial.

## Solución
Solo si se pide explícitamente.

Registrar dependencia.

---

# 92. DETECCIÓN DE ATASCO

Medir:

- tiempo;
- repeticiones;
- comandos similares;
- falta de progreso.

Después:

```text
¿Quieres una pista?
```

Nunca imponer.

---

# 93. SISTEMA ANTI-WALKTHROUGH

Randomizar:

- puertos;
- nombres;
- usuarios;
- passwords;
- rutas;
- flags;
- tokens;
- IDs;
- topologías.

---

# 94. LABORATORIOS PROCEDURALES

Ejemplo IDOR:

Variante 1:
```text
/invoice?id=101
```

Variante 2:
```text
/api/orders/UUID
```

Variante 3:
GraphQL.

Variante 4:
App móvil.

Concepto igual, implementación distinta.

---

# 95. INSTALACIÓN DE LABS

Cada lab debe incluir:

```text
Prerequisitos
Arquitectura
Recursos
Puertos
Docker Compose
VM requerida
Variables
Inicio
Validación
Reset
Destrucción
```

---

# 96. LIMPIEZA OBLIGATORIA

Todos los labs terminan con:

# Limpiar laboratorio

Explicar:

- detener;
- borrar volúmenes del lab;
- eliminar redes creadas;
- eliminar VM temporal;
- limpiar hosts;
- revertir snapshot;
- comprobar servicios expuestos.

Evitar comandos destructivos indiscriminados.

---

# 97. AISLAMIENTO DE LABS

Por defecto:

```text
Internet
   ✕
LAB NETWORK
├── attacker
├── target1
├── target2
└── services
```

Internet temporal solo cuando sea necesario para build.

---

# 98. LAB NETWORK TOPOLOGIES

Ejemplo:

```text
Kali
10.10.10.5
    │
    ▼
Web
10.10.10.20
172.16.0.20
    │
    ▼
Internal
172.16.0.0/24
    │
    ├── DB
    └── DC
```

Practicar:

- routing;
- pivoting;
- forwarding;
- SOCKS;
- tunneling;
- lateral movement.

---

# 99. LAB ORCHESTRATOR

Funciones:

```text
Create
Start
Stop
Reset
Destroy
Health Check
```

Definición declarativa.

Ejemplo:

```yaml
id: web-sqli-001
difficulty: beginner

services:
  web:
  database:

network:
  isolated: true

cleanup:
  remove_volumes: true
```

---

# 100. RETOS

Cada reto:

```text
Dificultad
Duración estimada
Áreas
Prerequisitos recomendados
Intentos
Pistas
Estado
```

No mostrar vulnerabilidades necesariamente.

---

# 101. RETOS DE INTEGRACIÓN

Ejemplo:

```text
Challenge: SmallShop
```

Prerequisitos sugeridos:

```text
Nmap
HTTP
ffuf
SQL
Linux basics
```

Camino posible interno:

```text
Enumeration
↓
Web
↓
Content discovery
↓
Login
↓
SQL injection
↓
Authentication bypass
↓
Sensitive information
↓
Credential reuse
↓
SSH
↓
Privilege escalation
```

No mostrar la cadena al estudiante.

---

# 102. FALSOS CAMINOS

Labs avanzados deben poder incluir:

- servicios no vulnerables;
- versiones llamativas pero parcheadas;
- rutas inútiles;
- credenciales antiguas;
- archivos señuelo;
- falsos positivos.

Evitar que toda pista lleve a la solución.

---

# 103. TROUBLESHOOTING LABS

Crear ejercicios donde **no existe vulnerabilidad**.

El estudiante debe poder concluir:

```text
Esto no es vulnerable.
```

Combatir sesgo de explotación.

---

# 104. VULNERABILITY RESEARCH MODE

Proporcionar:

- servicio;
- código;
- protocolo;
- binario;
- logs;

sin indicar vulnerabilidad.

Usuario debe:

```text
reproducir
investigar
formular hipótesis
crear PoC en lab
documentar root cause
proponer patch
```

---

# 105. ZERO-DAY-STYLE SYNTHETIC LABS

Crear vulnerabilidades deliberadas:

- parser errors;
- state machine bugs;
- logic flaws;
- race conditions;
- privilege boundary errors;
- auth bugs;
- unsafe deserialization;
- protocol confusion.

Solo software creado para laboratorio.

---

# 106. WIRESHARK / PCAP

Labs de:

- ARP;
- DNS;
- TCP;
- TLS;
- HTTP;
- SMB;
- Kerberos;
- LDAP;
- DHCP;
- ICMP.

Permitir adjuntar PCAP y responder preguntas.

---

# 107. CÓDIGO

Incluir:

- Python;
- Bash;
- PowerShell;
- JavaScript;
- SQL;
- C básico.

Objetivo:

automatizar, comprender protocolos y entender vulnerabilidades.

---

# 108. BUILD YOUR OWN TOOL

Retos:

```text
Crear port scanner básico
Crear content discovery básico
Parsear Nmap XML
Crear enumerador HTTP
Crear checker concurrente
```

Para comprender herramientas, no reemplazarlas.

---

# 109. PROGRAMACIÓN SEGURA

Mostrar vulnerable vs corregido.

Ejemplo:

```text
SQL concatenado
vs
prepared statement
```

El alumno debe comprender:

```text
por qué existe
cómo se explota
cómo se corrige
cómo se detecta
```

---

# 110. BLUE TEAM COMPLEMENTARIO

Cada técnica cuando aplique:

```text
Attack
Detection
Prevention
Evidence
```

---

# 111. DETECTION LAB

Después del ataque:

```text
Ahora eres Blue Team.
Encuentra evidencia.
```

Analizar:

- logs;
- PCAP;
- process tree;
- auth events.

---

# 112. PURPLE TEAM

Flujo:

```text
Attack
↓
Observe
↓
Detect
↓
Mitigate
↓
Attack again
```

Verificar mitigación.

---

# 113. MITRE ATT&CK

Mapear técnicas avanzadas cuando tenga sentido.

No sobrecargar principiantes.

---

# 114. GAMIFICACIÓN

Sobria y profesional.

Permitir:

- XP;
- niveles;
- achievements;
- retos;
- badges;
- milestones;
- skill tree.

Ejemplos:

```text
Packet Apprentice
First Shell
Root Cause
No Hint Required
Pivot Initiate
Active Directory Operator
100 Requests Analysed
First PCAP Investigation
```

---

# 115. ACHIEVEMENTS BASADOS EN HABILIDAD

Premiar:

```text
5 labs sin pistas
explicar TCP meses después
resolver sin scanner automático
encontrar manualmente fallo no detectado
```

No solo terminar contenido.

---

# 116. MODOS DE APRENDIZAJE

```text
Learn
Practice
Challenge
Exam
Review
Explore
```

---

# 117. ROLES DE IA

La IA puede funcionar como:

```text
Instructor
Socratic Tutor
Examiner
Pentest Mentor
Blue-Team Analyst
Code Reviewer
Incident Responder
CTF Hint Engine
Report Reviewer
```

---

# 118. SOCRATIC MODE

Si usuario se atasca, no dar respuesta directa.

Ejemplo:

No:

```text
Ejecuta ffuf.
```

Sí:

```text
¿Qué superficie web has enumerado?
¿Revisaste robots.txt?
¿Hay contenido no enlazado?
¿Qué técnica conoces para content discovery?
```

---

# 119. ENTRENAMIENTO DE COMANDOS

No solo:

```text
¿Cuál es la sintaxis?
```

También:

```text
¿Por qué usarías -Pn?
¿Cuándo NO usarías --min-rate alto?
¿Qué evidencia te haría cambiar de estrategia?
```

---

# 120. MANUAL-FIRST CHALLENGES

Ocasionalmente limitar herramientas.

Ejemplos:

- HTTP con curl;
- TCP con netcat;
- DNS con dig;
- SMB manual antes de automatización.

---

# 121. AUTOMATION MODE

Después:

- Python;
- Bash;
- PowerShell.

Automatizar lo comprendido previamente.

---

# 122. HISTORIAL

Guardar cronológicamente:

```text
2026-08-09
NET-01

ARP 62%
DNS 45%
TCP 78%

Errores:
ARP/TCP confusion
```

Comparar meses.

---

# 123. ROADMAP PERSONAL

Ejemplo:

```text
NET-01 ✓
NET-02 ✓
NET-03 ← actual
LINUX-01 ✓
WEB-01 ✓
AD-01 pendiente
```

Permitir acceso libre.

---

# 124. MODO CERTIFICACIÓN

Rutas para:

- eJPT;
- PNPT;
- CPTS;
- OSCP;
- BSCP;
- CRTO;
- otras.

No copiar contenido propietario.

Mapear skills públicas.

---

# 125. SESSION SUMMARY

Después de cada sesión:

```text
Aprendido
Reforzado
Errores
Puntuaciones
Nuevos conceptos
Debilidades
Próximo paso
Repasos programados
```

---

# 126. AI TUTOR MEMORY

Contexto para tutor:

```text
nivel actual
errores frecuentes
conceptos dominados
conceptos olvidados
últimas evaluaciones
pistas usadas
objetivo
fragmentación
retención
```

Nunca asumir mastery por haber completado una lección.

---

# 127. EXPLICACIONES POR NIVEL

```text
ELI5
Beginner
Intermediate
Advanced
Expert
Research
```

---

# 128. EXPERT MODE

Reducir explicación y aumentar:

- RFC;
- código fuente;
- protocolos;
- PCAP;
- debugging;
- reversing;
- investigación;
- exploit development controlado;
- detección;
- mitigación.

---

# 129. PRIMARY SOURCES

Relacionar con:

- RFC;
- NIST;
- MITRE;
- OWASP;
- CISA;
- vendor advisory;
- source code.

---

# 130. HOME

Mostrar:

```text
Continuar:
NET-01.4 Packet Analysis

Repasos:
ARP
DNS
TCP

Challenge recomendado:
First Foothold

Debilidad:
Subnetting

Última nota:
[[TCP Three-Way Handshake]]
```

---

# 131. EXPERIENCIA DE USUARIO OBJETIVO

Debe ser fácil:

```text
abrir
↓
ver qué debo repasar
↓
continuar donde quedé
↓
hacer ejercicio
↓
iniciar laboratorio
↓
tomar notas
↓
cerrar laboratorio
↓
guardar progreso
```

---

# 132. TEMAS VISUALES

Cybersecurity profesional.

Evitar cliché Matrix excesivo.

Dark/light.

Tema de juego sobrio.

---

# 133. STACK TÉCNICO SUGERIDO

Inicial:

```text
Frontend:
React / Next.js
TypeScript
Tailwind

Backend:
FastAPI
Python

DB:
PostgreSQL

Cache/tasks:
Redis si hace falta

Lab orchestration:
Docker / Docker Compose inicialmente

Markdown:
MDX/parser compatible

Realtime:
WebSockets cuando aplique
```

Se permite proponer arquitectura mejor con justificación.

---

# 134. SEGURIDAD DE LA PLATAFORMA

Implementar:

- autenticación;
- MFA opcional;
- CSRF protection;
- CSP;
- secure cookies;
- rate limiting;
- RBAC preparado;
- audit logs;
- secrets management;
- encryption de secretos;
- dependency scanning;
- SAST;
- container scanning;
- backups;
- aislamiento.

---

# 135. SINGLE USER INICIAL

Inicial:

```text
OWNER
```

Preparar arquitectura futura:

```text
Student
Instructor
Administrator
Organization
```

sin sobreingeniería inicial.

---

# 136. MODELO DE DATOS MÍNIMO

```text
User

Domain
Topic
Concept
ConceptRelationship
Lesson

Exercise
Question
QuestionVariant
Answer
Evaluation

Skill
SkillProgress
ConceptMastery
ConceptRelationshipScore

RetentionEvent
ReviewSession
ReviewItem
ReviewSchedule

ErrorPattern
ConfidenceMeasurement
TransferAssessment

Laboratory
LabInstance
LabAttempt

Challenge
ChallengeAttempt

Hint
HintUsage

Note
Tag

CheatSheet
Tool

Vulnerability
CVE
CWE

AttackTechnique
AttackChain

Achievement

LearningSession
FocusSession
LearningPreference
```

---

# 137. API

Versionada:

```text
/api/v1/learning
/api/v1/labs
/api/v1/notes
/api/v1/progress
/api/v1/challenges
/api/v1/reviews
```

---

# 138. AUDITORÍA

Registrar:

```text
lab created
lab started
hint requested
solution revealed
challenge completed
note changed
skill updated
review completed
retention degraded
```

---

# 139. EXPORTACIÓN

Permitir:

```text
Markdown
JSON
PDF
```

Especialmente Obsidian.

Mantener wikilinks.

---

# 140. IMPORTACIÓN

Importar Markdown existente preservando metadata.

---

# 141. DOCUMENTACIÓN VIVA

Mostrar:

```text
Última revisión del contenido
Última revisión del usuario
Estado
```

Permitir actualizar conocimientos.

---

# 142. VERSIONADO

Lecciones/labs:

```text
AD-KERB-03 v1.4
```

Con changelog.

---

# 143. DIFFICULTY ENGINE

Calcular según:

- conceptos;
- pasos;
- falsos positivos;
- scripting;
- enumeración;
- pivoting;
- hints;
- conocimientos cruzados.

---

# 144. PRIMER ROADMAP

```text
BASE-00 — Computer Fundamentals

NET-01 — Networking Fundamentals
NET-02 — Ethernet / MAC / ARP
NET-03 — IPv4 / CIDR / Subnetting
NET-04 — Routing
NET-05 — TCP / UDP
NET-06 — DNS
NET-07 — DHCP
NET-08 — HTTP / TLS
NET-09 — Packet Analysis
NET-10 — Nmap

LINUX-01 — Filesystem
LINUX-02 — Users
LINUX-03 — Permissions
LINUX-04 — Processes
LINUX-05 — Services
LINUX-06 — Networking
LINUX-07 — Bash
LINUX-08 — Privilege Escalation Fundamentals

WEB-01 — HTTP
WEB-02 — Requests / Responses
WEB-03 — Cookies / Sessions
WEB-04 — Authentication
WEB-05 — Authorization
...
```

Continuar hasta avanzado.

---

# 145. FASES DE IMPLEMENTACIÓN

## Fase 0 — Diseño obligatorio

Antes de código:

1. arquitectura;
2. modelo de datos;
3. mapa de módulos;
4. arquitectura de labs;
5. threat model;
6. adaptive learning engine;
7. sistema de notas;
8. knowledge graph;
9. spaced repetition;
10. evaluaciones;
11. wireframes;
12. roadmap;
13. acceptance criteria;
14. riesgos;
15. ADRs principales.

## Fase 1 — Core

- auth;
- sidebar;
- contenido;
- notas Markdown;
- topics;
- skills;
- evaluaciones;
- dashboard;
- progress;
- review;
- forgetting engine básico;
- random review;
- timer/focus mode;
- Docker labs básicos.

## Fase 2

- challenges;
- hints;
- gamificación;
- knowledge graph;
- cheatsheets;
- vulnerability DB;
- error memory;
- fragmentation score.

## Fase 3

- adaptive AI tutor;
- procedural labs;
- spaced repetition avanzado;
- attack path visualizer;
- transfer tests;
- confidence calibration.

## Fase 4

- multi-host labs;
- AD;
- pivoting;
- network ranges;
- blue/purple team.

## Fase 5

- synthetic unknown vulnerabilities;
- research labs;
- reversing;
- exploit development controlado.

---

# 146. ARCHIVOS FUENTE DE VERDAD

Crear y mantener:

```text
PROJECT_MASTER_CHECKLIST.md
PEDAGOGICAL_PRINCIPLES.md
LEARNING_ENGINE.md
LAB_SECURITY_MODEL.md
THREAT_MODEL.md
ARCHITECTURE.md
```

Las características de:

- retención;
- repetición;
- fragmentación;
- test aleatorio;
- concentración;
- timer;
- “No sé qué estudiar”;
- Cold Case;
- Error Memory;
- Transfer Learning;

deben estar marcadas como **CORE / NON-OPTIONAL**.

---

# 147. PROJECT_MASTER_CHECKLIST.md

Cada tarea:

```markdown
- [ ] Pendiente
- [x] Completado
```

No marcar completado hasta:

- implementación;
- tests;
- lint;
- typecheck;
- validación de seguridad;
- acceptance criteria comprobado.

---

# 148. CRITERIO CRÍTICO DE ACEPTACIÓN PEDAGÓGICA

La plataforma NO puede considerarse funcional si únicamente permite:

```text
leer
hacer quiz
marcar completado
```

Debe demostrar al menos:

```text
aprendizaje
↓
evaluación
↓
registro de errores
↓
repaso programado
↓
nueva evaluación diferente
↓
medición de retención
↓
transferencia
↓
integración
```

---

# 149. CRITERIO DE ACEPTACIÓN DE ATENCIÓN

Debe existir como mínimo:

- `Continuar`;
- `No sé qué estudiar`;
- `Solo 5 minutos`;
- Focus Mode;
- Count Up;
- Pomodoro configurable;
- recordatorio de pausa;
- reanudación exacta de sesión;
- recap contextual.

No deben eliminarse como “nice to have”.

---

# 150. CRITERIO DE ACEPTACIÓN DE FRAGMENTACIÓN

Debe existir una prueba que demuestre:

1. usuario puntúa alto individualmente en varios conceptos;
2. falla escenario integrador;
3. sistema detecta fragmentación;
4. genera actividad integradora;
5. reevalúa posteriormente.

---

# 151. CRITERIO DE ACEPTACIÓN DE RETENCIÓN

Demostrar:

1. concepto aprendido;
2. ReviewSchedule creado;
3. nueva variante generada;
4. respuesta registrada;
5. retention_score actualizado;
6. forgetting_risk recalculado;
7. dashboard actualizado.

---

# 152. CRITERIO DE ACEPTACIÓN DE ERROR MEMORY

Demostrar:

1. error repetido;
2. ErrorPattern creado;
3. pregunta futura diseñada contra ese error;
4. error deja de repetirse;
5. estado actualizado.

---

# 153. CRITERIO DE ACEPTACIÓN DE COLD CASE

Demostrar:

1. lab completado;
2. meses/días simulados;
3. nueva variante;
4. walkthrough anterior no suficiente;
5. retención y transferencia evaluadas.

---

# 154. CRITERIO DE ACEPTACIÓN “NO SÉ QUÉ ESTUDIAR”

El sistema debe elegir **una sola actividad** usando:

- forgetting risk;
- debilidad;
- fragmentación;
- roadmap;
- tiempo;
- concentración;
- prerequisitos.

Debe explicar brevemente por qué la eligió.

---

# 155. PRINCIPIO DE PRIVACIDAD Y DATOS

El sistema pedagógico puede registrar rendimiento, pero debe:

- minimizar datos;
- permitir borrar historial;
- permitir exportar;
- no inferir diagnósticos médicos;
- no etiquetar al usuario clínicamente;
- tratar métricas de concentración como preferencias/uso, no diagnóstico.

---

# 156. FILOSOFÍA FINAL

La plataforma debe producir una persona capaz de mirar:

```text
IP desconocida
aplicación desconocida
red desconocida
código desconocido
```

y pensar:

```text
¿Qué sé?
¿Qué no sé?
¿Qué puedo observar?
¿Qué hipótesis puedo formular?
¿Cómo la verifico?
¿Qué evidencia tengo?
¿Qué implica?
¿Cómo se corrige?
```

No entrenar recetas.

Entrenar **investigación técnica, razonamiento, autonomía y retención**.

---

# 157. LAS CUATRO PREGUNTAS PRINCIPALES DEL PRODUCTO

La métrica más importante NO es:

```text
¿Cuánto contenido vio?
```

Debe ser:

```text
¿Qué puede explicar hoy?

¿Qué puede hacer sin ayuda?

¿Qué sigue recordando meses después?

¿Puede aplicar ese conocimiento en un problema que nunca había visto?
```

Toda decisión de diseño pedagógico debe poder justificarse respecto a estas cuatro preguntas.

---

# 158. ENTREGABLE INICIAL OBLIGATORIO DEL AGENTE

Antes de escribir código, entregar:

1. arquitectura propuesta;
2. modelo de datos;
3. mapa de módulos;
4. arquitectura de laboratorios;
5. threat model;
6. adaptive learning engine;
7. forgetting/retention engine;
8. fragmentation detection;
9. sistema de notas;
10. knowledge graph;
11. sistema de repetición espaciada;
12. modelo de evaluaciones;
13. sistema de preguntas aleatorias;
14. Focus/Timer UX;
15. lógica de “No sé qué estudiar”;
16. wireframes;
17. roadmap por fases;
18. acceptance criteria;
19. riesgos técnicos;
20. decisiones abiertas;
21. ADRs iniciales.

Después comenzar Fase 1.

---

# 159. INSTRUCCIÓN FINAL A LA IA

Este documento es la fuente de verdad funcional y pedagógica del proyecto.

Si durante el desarrollo surge presión para simplificar, priorizar en este orden:

1. seguridad y aislamiento;
2. aprendizaje adaptativo;
3. retención;
4. fragmentación/conexión;
5. evaluaciones;
6. notas;
7. labs;
8. metodología;
9. concentración/reentrada;
10. gamificación.

No sacrificar el motor pedagógico para producir una plataforma que únicamente “muestre cursos”.

El objetivo es crear un sistema que pueda acompañar al usuario durante años, desde fundamentos hasta investigación avanzada, y que sea capaz de detectar no solo lo que estudió sino lo que realmente comprende, retiene, conecta y puede utilizar de forma autónoma.

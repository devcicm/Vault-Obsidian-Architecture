 Vault Obsidian Architecture es un patrón de documentación y memoria operativa para agentes LLM que convierte el
  conocimiento del proyecto en una bóveda viva, navegable y trazable. En lugar de depender de memoria efímera o notas
  sueltas, el sistema organiza la información en Markdown con frontmatter YAML, enlaces tipo [[wiki-links]], versionado
  automático, índices de búsqueda y grafo de relaciones. Esto permite que la documentación no solo se lea, sino que
  también funcione como una base de conocimiento activa que acompaña al agente entre sesiones, reduce errores repetidos
  y preserva decisiones técnicas reales.

  La arquitectura está pensada para resolver un problema concreto: cuando un proyecto crece, la información se dispersa,
  se contradice y se pierde contexto. Este vault lo evita mediante una estructura de carpetas numeradas, contratos
  estrictos de escritura, clasificación por temas, runbooks, decisiones arquitectónicas, observabilidad, infraestructura
  y exclusiones explícitas. El resultado es una documentación que no es decorativa, sino operativa: se puede auditar,
  buscar, enlazar, migrar, abrir en Obsidian y usar como memoria persistente para sistemas de automatización o agentes
  inteligentes.

  Lo que hace destacar a este enfoque es que no exige una base de datos compleja ni herramientas pesadas para funcionar.
  Todo vive en archivos legibles por humanos y compatibles con Git, pero organizados de forma suficiente para que un
  agente pueda recuperar contexto relevante automáticamente. Eso convierte al vault en una especie de RAG local, simple
  en infraestructura pero fuerte en disciplina documental.

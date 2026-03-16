# Улучшение системы памяти: анализ qwen-agent и предложения по доработке

## 1. Введение

Данный документ содержит аналитику системы памяти агента qwen-agent (форк Gemini CLI от Alibaba Group) и предложения по переносу ключевых механизмов в текущий Python-проект. Директория `./qwen-agent` содержит исходный код стороннего ИИ-агента, не являющегося частью текущего проекта, и используется исключительно как источник идей для анализа. Цель — устранить ограничение однократности сессий: агент не помнит ничего между запусками, не может накапливать знания о проекте и теряет контекст при переполнении окна LLM.

---

## 2. Система памяти qwen-agent

qwen-agent реализует трёхуровневую модель памяти: краткосрочная (RAM), долгосрочная (файлы QWEN.md) и сессионная (JSONL + Todo). Каждый уровень решает отдельную задачу и работает независимо.

### 2.1 Краткосрочная память (in-memory)

- **Хранилище:** RAM, объект `GeminiChat.history: Content[]`
- **Время жизни:** до завершения процесса
- **Механизм сжатия:** `ChatCompressionService` срабатывает автоматически при достижении ≥70% заполнения контекстного окна
- **Формат сжатия:** LLM генерирует XML-документ `<state_snapshot>` со следующими разделами:

```xml
<state_snapshot>
  <overall_goal>Основная цель текущей сессии</overall_goal>
  <key_knowledge>Ключевые факты, выясненные в ходе работы</key_knowledge>
  <file_system_state>Состояние файловой системы: созданные, изменённые файлы</file_system_state>
  <recent_actions>Последние выполненные действия</recent_actions>
  <current_plan>Текущий план на следующие шаги</current_plan>
</state_snapshot>
```

Этот снимок заменяет всю историю диалога, сохраняя только семантически важную информацию.

### 2.2 Долгосрочная память (QWEN.md файлы)

- **Глобальная память:** `~/.qwen/QWEN.md` — общая для всех проектов
- **Проектная память:** `<project_dir>/QWEN.md` — специфична для конкретного проекта
- **Загрузка:** иерархическая — от домашней директории до текущей рабочей директории; читаются все промежуточные `QWEN.md` файлы

**Алгоритм загрузки при старте сессии:**

```
loadServerHierarchicalMemory(cwd):
  paths = []
  current = home_dir
  while current != cwd:
      if exists(current / "QWEN.md"):
          paths.append(current / "QWEN.md")
      current = next_segment(current, cwd)
  if exists(cwd / "QWEN.md"):
      paths.append(cwd / "QWEN.md")

  memory_text = ""
  for path in paths:
      memory_text += f"--- Context from: {path} ---\n"
      memory_text += read(path) + "\n"
  return memory_text
```

Итоговый текст вставляется в системный промпт через `getCoreSystemPrompt(userMemory)`.

**Алгоритм записи памяти (`save_memory`):**

Инструмент `save_memory(fact, scope)` доступен агенту и добавляет bullet-point к нужному файлу:

```
save_memory(fact, scope="global"):
  target = project_dir / "QWEN.md"  если scope == "project"
           home_dir / ".qwen/QWEN.md"  если scope == "global"

  if not exists(target):
      create(target, content="# Memory\n\n## Qwen Added Memories\n")
  elif "## Qwen Added Memories" not in read(target):
      append(target, "\n## Qwen Added Memories\n")

  append(target, f"- {fact}\n")
```

Формат файла после нескольких записей:

```markdown
# Project Memory

## Qwen Added Memories
- Проект использует Flask 3.1.1 и OpenAI SDK
- Основной файл оркестрации: algorythm.py, класс Copilot
- Агенты определены в agents.py: AnalyticAgent, CoderAgent
```

### 2.3 Сессионная память (JSONL + Todo)

- **История чата:** `~/.qwen/projects/<hash_от_project_path>/chats/<sessionId>.jsonl`
- **Todo-задачи:** `~/.qwen/todos/<sessionId>.json`
- **Возобновление сессии:** флаги `--continue` (продолжить последнюю) и `--resume <sessionId>` (выбрать конкретную)

**Session resume алгоритм:**

```
resume_session(sessionId):
  history = load_jsonl(chats_dir / f"{sessionId}.jsonl")
  todos = load_json(todos_dir / f"{sessionId}.json")

  if has_compression_checkpoint(history):
      base = get_latest_checkpoint(history)   // state_snapshot из сжатия
      tail = messages_after_checkpoint(history)
      conversation = [base] + tail
  else:
      conversation = history

  initialize_agent(conversation, todos)
```

### 2.4 Схема взаимодействия компонентов

```
┌─────────────────────────────────────────────────────────┐
│                    ЗАПУСК СЕССИИ                         │
│                                                          │
│  loadServerHierarchicalMemory()                          │
│    ├─ ~/.qwen/QWEN.md          ← глобальная память       │
│    ├─ ~/project/QWEN.md        ← проектная память        │
│    └─ ./subdir/QWEN.md         ← локальная память        │
│               ↓                                          │
│  getCoreSystemPrompt(userMemory)                         │
│               ↓                                          │
│  ┌────────────────────────────────────┐                  │
│  │       ДИАЛОГ В ПАМЯТИ (RAM)        │                  │
│  │  GeminiChat.history: Content[]     │                  │
│  │                                    │                  │
│  │  ≥70% токенов                      │                  │
│  │      → ChatCompressionService      │                  │
│  │          → <state_snapshot>        │                  │
│  │          → заменяет историю        │                  │
│  │                                    │                  │
│  │  save_memory(fact)                 │                  │
│  │      → append to QWEN.md          │                  │
│  │                                    │                  │
│  │  ChatRecordingService              │                  │
│  │      → append to JSONL            │                  │
│  └────────────────────────────────────┘                  │
│               ↓                                          │
│  ЗАВЕРШЕНИЕ СЕССИИ                                       │
│    ├─ JSONL: полная история сохранена                    │
│    ├─ QWEN.md: новые факты записаны                      │
│    └─ Todos: статусы обновлены                           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Текущее состояние памяти в проекте

### 3.1 Что реализовано

**Краткосрочная память (история чата в RAM)**

В `agents.py` каждый агент (`AnalyticAgent`, `CoderAgent`) хранит историю диалога как локальная переменная `conversation` в методе `run()` и передаёт её в LLM при каждом вызове. Это стандартный подход messages array в OpenAI API. Память живёт ровно столько, сколько выполняется задача, и умирает вместе с вызовом метода.

Реализованы механизмы компакции контекста:
- `conversation_filter()` в `BaseAgent` — применяет `compact_conversation_remove_redundant()` из `context_helper.py` (удаляет устаревшие чтения, дедуплицирует повторные чтения одного файла и одинаковые shell-команды)
- `TOOL_SUMMARIZE` + `_context_overflow_summarize` в `agents.py` — автоматически срабатывают при превышении `MAX_CONTEXT_WINDOW_SIZE`, генерируя сжатый снимок состояния через LLM

**Системный промпт из `AGENTS.md`**

В `algorythm.py` класс `Copilot` читает `AGENTS.md` (опциональный файл в корне проекта) при инициализации и использует его содержимое как часть системного промпта SUPERVISOR-а. Это единственная форма «долгосрочного» контекста — статичный файл, который нужно редактировать вручную.

**Логи сессий в `conversations_log/`**

Файл `llm.py` пишет полные логи взаимодействий с LLM в `conversations_log/full_log.log`. Логи предназначены только для отладки и не читаются агентами при следующем запуске.

**MAX_ITERATION лимит**

В `algorythm.py` реализован счётчик итераций как предохранитель от бесконечных циклов. Это не механизм памяти, но важная часть управления состоянием.

### 3.2 Что отсутствует

| Механизм | Статус |
|---|---|
| Долгосрочная память между сессиями | ❌ Не реализована |
| Автосжатие контекста при переполнении | ⚠️ Частично — базовый механизм реализован через `TOOL_SUMMARIZE` + `_context_overflow_summarize` в `agents.py` |
| Сохранение фактов о проекте между запусками | ❌ Не реализовано |
| Иерархическая загрузка контекста по директориям | ❌ Не реализована |
| Session resume (продолжение прерванной задачи) | ❌ Не реализован |
| Инструмент `save_memory` у агентов | ❌ Не реализован |
| Накопление знаний об архитектуре проекта | ❌ Не реализовано |

---

## 4. Предложения по доработке

### 4.1 Долгосрочная память (аналог QWEN.md)

**Концепция:** ввести файл `.copilot_memory.md` в корне проекта и опциональный глобальный `~/.copilot/memory.md`. Агенты смогут читать накопленные знания при старте и дозаписывать новые факты в процессе работы.

**Формат файла `.copilot_memory.md`:**

```markdown
# Project Memory

## Architecture
- Supervisor pattern: algorythm.py → agents.py
- LLM integration: llm.py (OpenAI-compatible API)

## Copilot Added Memories
- Агент CODER не должен создавать утилитарные скрипты
- Основной конфиг проекта: AGENTS.md (опциональный файл в корне проекта)
```

**Загрузка в системный промпт:**

В `algorythm.py` при инициализации `Copilot`:

```python
def _load_memory(self) -> str:
    memory_parts = []
    global_memory = Path.home() / ".copilot" / "memory.md"
    project_memory = Path(self.base_path) / ".copilot_memory.md"

    for path in [global_memory, project_memory]:
        if path.exists():
            memory_parts.append(f"--- Memory from: {path.name} ---\n{path.read_text()}")

    return "\n\n".join(memory_parts)
```

Результат добавляется в системный промпт SUPERVISOR-а рядом с содержимым `AGENTS.md` (опциональный файл в корне проекта).

**Инструмент `save_memory` для агентов:**

В `agents.py` добавить метод в `BaseAgent`:

```python
def save_memory(self, fact: str, scope: str = "project") -> str:
    if scope == "global":
        target = Path.home() / ".copilot" / "memory.md"
        target.parent.mkdir(exist_ok=True)
    else:
        target = Path(self.base_path) / ".copilot_memory.md"

    if not target.exists():
        target.write_text("# Project Memory\n\n## Copilot Added Memories\n")
    elif "## Copilot Added Memories" not in target.read_text():
        with target.open("a") as f:
            f.write("\n## Copilot Added Memories\n")

    with target.open("a") as f:
        f.write(f"- {fact}\n")

    return f"Memory saved to {target}"
```

Инструмент нужно добавить в схемы инструментов `AnalyticAgent` и `CoderAgent` в `prompts/`.

**Файлы для изменения:**
- `agents.py` — добавить метод `save_memory` в `BaseAgent`, зарегистрировать как tool в агентах
- `algorythm.py` — добавить `_load_memory()`, включить результат в системный промпт
- `tools/tools.py` — добавить JSON-схему инструмента `save_memory`
- `prompts/analytic_system.txt` — описать когда использовать `save_memory`
- `prompts/coder_system.txt` — описать когда использовать `save_memory`

---

### 4.2 Автосжатие контекста

**Концепция:** при приближении к лимиту токенов контекстного окна — автоматически сжимать историю диалога в структурированный снимок состояния, сохраняя семантику без исходных сообщений.

**Триггер сжатия:**

Рекомендуемый порог — 70% заполнения контекстного окна. Оценку числа токенов удобнее делать по количеству символов с коэффициентом (≈4 символа на токен), чтобы не зависеть от токенизатора конкретной модели:

```python
MAX_CONTEXT_CHARS = 120_000  # ~30k токенов при 4 символа/токен
COMPRESSION_THRESHOLD = 0.70

def _needs_compression(self, conversation: list) -> bool:
    total_chars = sum(len(str(m.get("content", ""))) for m in conversation)
    return total_chars > MAX_CONTEXT_CHARS * COMPRESSION_THRESHOLD
```

**Формат state_snapshot (Markdown-вариант для совместимости с моделями):**

```markdown
## State Snapshot

**Overall Goal:** <цель текущей задачи>

**Key Knowledge:**
- <факт 1>
- <факт 2>

**File System State:**
- Created: file1.py, file2.py
- Modified: agents.py (добавлен метод X)

**Recent Actions:**
- Проанализирована структура проекта
- Создан план реализации

**Current Plan:**
1. Следующий шаг
2. ...
```

**Где реализовать:**

> **Примечание:** Базовый механизм автосжатия уже реализован в `agents.py` через `TOOL_SUMMARIZE` + `_context_overflow_summarize`: при превышении `MAX_CONTEXT_WINDOW_SIZE` агент вызывает LLM для генерации снимка состояния. Предложенный ниже `ContextCompressionService` является расширением этого подхода с вынесением в отдельный модуль и настройкой порога срабатывания.

Вынести в отдельный сервис `context_compression.py` с классом `ContextCompressionService`:

```python
class ContextCompressionService:
    def __init__(self, llm_client):
        self.llm = llm_client

    def compress(self, conversation: list, system_prompt: str) -> list:
        snapshot = self.llm.generate_snapshot(conversation)
        return [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": f"[Compressed context]\n{snapshot}"}
        ]
```

В `agents.py` вызывать перед каждым запросом к LLM:

```python
if self._needs_compression(self.conversation):
    self.conversation = self.compression_service.compress(
        self.conversation, self.system_prompt
    )
```

**Файлы для изменения:**
- `context_compression.py` — новый файл, `ContextCompressionService`
- `agents.py` — интегрировать вызов сжатия в `BaseAgent` перед LLM-запросом
- `llm.py` — добавить метод для генерации снимка состояния

---

### 4.3 Session Resume

**Концепция:** сохранять состояние сессии после завершения задачи, чтобы при следующем запросе можно было продолжить с того же места.

**Формат хранения сессии:**

```
conversations_log/
  sessions/
    <project_hash>/
      <session_id>.jsonl     ← история сообщений
      <session_id>.meta.json ← метаданные сессии
```

Формат `meta.json`:

```json
{
  "session_id": "2024-01-15-143022",
  "project_path": "/path/to/project",
  "task": "Добавить систему памяти",
  "status": "completed",
  "created_at": "2024-01-15T14:30:22",
  "last_updated": "2024-01-15T15:12:45",
  "iterations": 8,
  "has_checkpoint": true
}
```

**Алгоритм сохранения:**

В `algorythm.py` класс `Copilot` после каждой итерации:

```python
def _save_session(self):
    session_dir = Path("conversations_log/sessions") / self._project_hash()
    session_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = session_dir / f"{self.session_id}.jsonl"
    with jsonl_path.open("a") as f:
        for msg in self.new_messages_since_last_save:
            f.write(json.dumps(msg, ensure_ascii=False) + "\n")
```

**Алгоритм восстановления:**

```python
def resume_session(session_id: str, project_path: str) -> "Copilot":
    session_dir = Path("conversations_log/sessions") / project_hash(project_path)
    history = load_jsonl(session_dir / f"{session_id}.jsonl")
    meta = load_json(session_dir / f"{session_id}.meta.json")

    copilot = Copilot(project_path)
    copilot.conversation = history
    copilot.session_id = session_id
    return copilot
```

**Интеграция в API:**

В `llm_api_server.py` добавить параметр `resume_session_id` в тело запроса `POST /api/agent`:

```json
{
  "message": "продолжай",
  "project_base_path": "/path/to/project",
  "max_working_time": 120,
  "resume_session_id": "2024-01-15-143022"
}
```

**Файлы для изменения:**
- `algorythm.py` — добавить `_save_session()`, `resume_session()`, `_project_hash()`
- `llm_api_server.py` — добавить параметр `resume_session_id` в `/api/agent`

> **Примечание:** `conversation.py` в проекте отвечает за HTML-рендеринг UI-сообщений (`DTOInstruction` → HTML/text) и не предназначен для сериализации истории чата агентов. Сериализацию истории следует реализовать непосредственно в `algorythm.py` или отдельном модуле.

---

### 4.4 Улучшение `AGENTS.md` (контекстный файл проекта)

**Концепция:** расширить существующий `AGENTS.md` (опциональный файл в корне проекта) секцией для накопления структурированных знаний об архитектуре, соглашениях и важных решениях.

```xml
<project>
  <name>AI Development Assistant</name>
  <description>Multi-agent coding assistant</description>
  <stack>Python, Flask, OpenAI SDK</stack>

  <memory>
    <architecture>
      <fact>Supervisor pattern: Copilot → AnalyticAgent + CoderAgent</fact>
      <fact>LLM: OpenAI-compatible API через llm.py</fact>
    </architecture>
    <conventions>
      <fact>Промпты хранятся в prompts/ как Jinja2 шаблоны</fact>
      <fact>CODER не создаёт утилитарные скрипты</fact>
    </conventions>
    <decisions>
      <fact date="2024-01-15">Выбран MCP для интеграции с IDE вместо REST</fact>
    </decisions>
  </memory>
</project>
```

**Инструмент `update_project_memory`:**

Агенты смогут добавлять факты через специальный инструмент, а `algorythm.py` будет парсить `<memory>` секцию и включать в системный промпт структурированно.

**Файлы для изменения:**
- `algorythm.py` — расширить парсинг для чтения секции памяти из `AGENTS.md` (опциональный файл в корне проекта)
- `tools/tools.py` — добавить схему `update_project_memory`

---

## 5. Приоритизация

| Улучшение | Приоритет | Сложность | Ожидаемый эффект |
|---|---|---|---|
| **4.1 Долгосрочная память (.copilot_memory.md)** | 🔴 High | Средняя | Агент помнит соглашения и архитектуру между сессиями; меньше повторного анализа |
| **4.2 Автосжатие контекста** | 🔴 High | Высокая | Устранение ошибок переполнения контекста при длинных задачах; работа с большими кодовыми базами |
| **4.4 Секция памяти в `AGENTS.md`** | 🟡 Medium | Низкая | Быстрое улучшение с минимальными изменениями; структурированное хранение решений по архитектуре |
| **4.3 Session Resume** | 🟡 Medium | Высокая | Возможность продолжать прерванные задачи; важно для долгих рефакторингов |
| **Глобальная память `~/.copilot/memory.md`** | 🟢 Low | Низкая | Полезно при работе с несколькими проектами одновременно |

---

## 6. Схема целевой архитектуры памяти

```
┌──────────────────────────────────────────────────────────────────┐
│                    ЗАПУСК / RESUME СЕССИИ                         │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                  ЗАГРУЗКА ПАМЯТИ                             │  │
│  │                                                              │  │
│  │  ~/.copilot/memory.md       ← глобальная память             │  │
│  │  <project>/.copilot_memory.md  ← проектная память           │  │
│  │  <project>/AGENTS.md (optional)   ← архитектура             │  │
│  │  [optional] sessions/<hash>/<id>.jsonl  ← resume context    │  │
│  └──────────────────────────┬──────────────────────────────────┘  │
│                             ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              SUPERVISOR (algorythm.py)                       │  │
│  │                                                              │  │
│  │  system_prompt = xml_content + loaded_memory                 │  │
│  │  conversation: list[Message]  ←  краткосрочная RAM           │  │
│  │                                                              │  │
│  │  → call_agent(ANALYTIC)   → call_agent(CODER)   → exit()   │  │
│  └──────────┬──────────────────────────┬────────────────────────┘  │
│             ↓                          ↓                           │
│  ┌─────────────────────┐       ┌─────────────────────────┐              │
│  │  ANALYTIC Agent     │       │    CODER Agent          │              │
│  │                     │       │                         │              │
│  │  read_file          │       │  read_file              │              │
│  │  list_in_directory  │       │  list_in_directory      │              │
│  │  search_file        │       │  write_file             │              │
│  │  save_memory ───────┼──┐    │  replace_code_in_file   │              │
│  │  report             │  │    │  save_memory ───────────┼──┐           │
│  └─────────────────────┘  │    │  report                 │  │           │
│                        │    └──────────────────────┘  │           │
│             ┌──────────┘                  ┌───────────┘           │
│             ↓                             ↓                        │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                 ЗАПИСЬ ПАМЯТИ                                │  │
│  │                                                              │  │
│  │  save_memory(fact, "project")                                │  │
│  │      → append to .copilot_memory.md                         │  │
│  │                                                              │  │
│  │  save_memory(fact, "global")                                 │  │
│  │      → append to ~/.copilot/memory.md                       │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                             ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │            УПРАВЛЕНИЕ КОНТЕКСТОМ (RAM)                       │  │
│  │                                                              │  │
│  │  ContextCompressionService                                   │  │
│  │      if total_chars > 70% * MAX_CONTEXT_CHARS:               │  │
│  │          conversation = compress(conversation)               │  │
│  │              → <state_snapshot> заменяет историю             │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                             ↓                                      │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                 СЕССИОННОЕ ХРАНИЛИЩЕ                         │  │
│  │                                                              │  │
│  │  ChatRecordingService                                        │  │
│  │      → conversations_log/sessions/<hash>/<id>.jsonl          │  │
│  │      → conversations_log/sessions/<hash>/<id>.meta.json      │  │
│  │                                                              │  │
│  │  Доступно для resume: POST /api/agent                        │  │
│  │      { "resume_session_id": "<id>" }                         │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘

Уровни памяти и время жизни:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Глобальная │ ~/.copilot/memory.md          │ Постоянная        │
  │  Проектная  │ .copilot_memory.md            │ Постоянная        │
  │  Сессионная │ conversations_log/sessions/   │ До удаления       │
  │  Оперативная│ Agent.conversation (RAM)      │ Время задачи      │
  └─────────────────────────────────────────────────────────────────┘
```
# Specification: Upload Image for LLM Context

## Overview

This feature allows users to attach an image to their task message in the web UI chat interface. The image is sent alongside the text prompt to the SUPERVISOR agent and injected into the LLM conversation as a multimodal (`image_url`) content block, enabling vision-capable LLM models to "see" the image as part of the task context.

---

## User Stories

- **As a developer**, I want to attach a screenshot or diagram to my task so the AI can visually understand the context of what I need built or fixed.
- **As a developer**, I want to see a thumbnail preview of the image I'm about to send before submitting.
- **As a developer**, I want to be able to remove the attached image before sending the message.
- **As a developer**, I want the image to appear in my chat message bubble so I can confirm it was sent.

---

## Scope & Constraints

- Only the **SUPERVISOR** agent receives the image in its first user message. Sub-agents (ANALYTIC, CODER, REVIEWER) do **not** receive the image — it is not forwarded to them.
- **No backend image storage**: the raw base64 Data URL is held transiently in session memory only and is never written to disk.
- **Maximum image size**: 5 MB (client-side validation).
- **Accepted formats**: any `image/*` MIME type (client-side file picker filter).
- **No new environment variables** are introduced by this feature.
- **No new DTO fields** are added; `DTOInstruction` is unchanged.
- Image upload is only available via the **web UI** (`/send_message`). The REST API endpoint (`POST /api/agent`) does not support image attachment.

---

## Data Flow

```
User selects image file (≤5 MB, image/* type)
  → FileReader reads file as Data URL (base64)
  → Preview thumbnail shown above textarea
  → User types message and clicks Send

POST /send_message  { message: "...", image: "data:image/png;base64,..." }
  → Server validates: image must start with "data:image/"
  → Server stores image in session as "pending_image"
  → Response: { status: "success" }

SSE event_stream() picks up task
  → Copilot.run() reads session["pending_image"]
  → Builds multimodal user content:
      [
        { "type": "text",      "text": "<instruction>" },
        { "type": "image_url", "image_url": { "url": "data:image/..." } }
      ]
  → SUPERVISOR LLM receives multimodal message
  → After task completes: session["pending_image"] = None
```

When no image is selected, the fetch body still includes `"image": null`. The server handles `null` correctly: the `None` check skips validation, and the falsy guard skips storing — behaviour is identical to the pre-feature state.

---

## Technical Implementation

### `llm_api_server.py`

**Route `/send_message` (POST)**:
- Extract `image = data.get('image')` from JSON body.
- **Validation**: if `image` is not `None`, it must be a `str` starting with `'data:image/'`; otherwise return HTTP 400:
  ```json
  { "status": "error", "message": "Invalid image format" }
  ```
- If valid and truthy (non-empty), store via:
  ```python
  if image:
      SESSION_MANAGER_INSTANCE.add_session_parameter(user_session_id, 'pending_image', image)
  ```
  Note: the `if image is not None:` guard runs for any non-`None` value, including `""`. An empty string fails the `startswith('data:image/')` check and returns HTTP 400. Only `null` / Python `None` bypasses validation entirely.

**`event_stream()` — cleanup after task**:
- After `process_task()` completes, inside `event_stream()` immediately after `commit_message()`, reset the pending image:
  ```python
  SESSION_MANAGER_INSTANCE.commit_message(session_id)
  SESSION_MANAGER_INSTANCE.add_session_parameter(session_id, 'pending_image', None)
  ```

---

### `algorythm.py` — `Copilot.run()`

- Read: `pending_image = self.session.get('pending_image') if self.session else None`
- If `pending_image` is truthy, build multimodal content:
  ```python
  user_content = [
      {"type": "text",      "text": self.instruction},
      {"type": "image_url", "image_url": {"url": pending_image}}
  ]
  ```
- Otherwise: `user_content = self.instruction` (plain string — existing behaviour unchanged).
- Use `user_content` as the `'content'` value of the first `'user'` message in `conversation_log`.

---

### `templates/app.html`

Add the following DOM elements inside `.input-container`:

- **`#image-preview-container`** (hidden by default) — shown when an image is selected:
  - `<img id="image-preview">` — thumbnail
  - `<button id="clear-image-btn">✕</button>` — removes the pending image
- **`.input-toolbar`** div below the `<textarea>`:
  - `<button id="upload-image-btn" class="default upload-image-btn">📎 Image</button>`
- **`#image-upload-input`** — `<input type="file" accept="image/*" style="display:none">` (placed before the closing </body> tag (there is no <form> element in the page))

```html
<div class="input-container">
    <div id="image-preview-container">
        <img id="image-preview" src="" alt="preview">
        <button id="clear-image-btn" type="button">✕</button>
    </div>
    <textarea id="message-input" ...></textarea>
    <div class="input-toolbar">
        <button id="upload-image-btn" class="default upload-image-btn" type="button">📎 Image</button>
    </div>
</div>
...
<input type="file" id="image-upload-input" accept="image/*" style="display:none">
```

---

### `templates/assets/app.js`

**Constructor additions**:
```js
this.pendingImageDataUrl = null;
this.uploadImageBtn = document.getElementById('upload-image-btn');
```

**`setupEventListeners()`**:
- `uploadBtn` click → `fileInput.click()`
- `fileInput` `change` → `this.handleImageSelected(e)`
- `clearBtn` click → `this.clearPendingImage()`
- `onStartConversation()`: `this.uploadImageBtn.style.display = 'none'`
- `onEndConversation()`: `this.uploadImageBtn.style.display = 'block'`

Note: `setupEventListeners()` re-queries DOM elements locally (e.g. `const uploadBtn = document.getElementById('upload-image-btn')`) for the event listener wiring and uses a null-guard (`if (uploadBtn)`). The constructor-stored `this.uploadImageBtn` is used separately in `onStartConversation()` / `onEndConversation()` with optional chaining.

**`handleImageSelected(event)`** (new method):
1. Get `file = event.target.files[0]`; return if none.
2. Validate `file.type.startsWith('image/')` — alert if not.
3. Validate `file.size <= 5 * 1024 * 1024` (5 MB) — alert if exceeded.
4. Use `FileReader.readAsDataURL(file)`:
   - On load: set `this.pendingImageDataUrl = e.target.result`
   - Show preview: set `#image-preview` `src`, show `#image-preview-container` (`display: flex`)
5. Reset `event.target.value = ''`

**`clearPendingImage()`** (new method):
- `this.pendingImageDataUrl = null`
- Clear `#image-preview` `src`, hide `#image-preview-container`

**`sendMessage(message)`** updates:
- Call `addMessage({ message, image: this.pendingImageDataUrl }, 'user')` **before** the fetch (optimistic rendering — the user bubble is displayed immediately).
- Include `image: this.pendingImageDataUrl` in the JSON body of `POST /send_message`.
- On success: call `this.clearPendingImage()` then `this.onStartConversation()`.

**`addMessage(message, type)`** — user message rendering:
- When `type === 'user'`, generate `imageHtml`:
  ```js
  const imageHtml = message.image
      ? `<img src="${message.image}" class="user-image-preview" alt="attached image">`
      : '';
  ```
- Prepend `imageHtml` to the message content in the bubble HTML.

---

### `templates/assets/main.css`

New CSS rules to add:

```css
/* Toolbar wrapping the image upload button */
.input-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 6px;
}

/* Upload button sizing */
.upload-image-btn {
    font-size: 0.85em;
    padding: 4px 12px;
    cursor: pointer;
}

/* Preview container — hidden by default, shown as flex when image selected */
#image-preview-container {
    display: none;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 8px;
    padding: 6px 8px;
    border: 1px dashed #aaa;
    border-radius: 6px;
    background: rgba(0,0,0,0.03);
    position: relative;
}

/* Preview image thumbnail */
#image-preview {
    max-height: 120px;
    max-width: 220px;
    border-radius: 4px;
    object-fit: contain;
    display: block;
}

/* Clear button (✕) */
.clear-image-btn {
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    font-size: 12px;
    line-height: 22px;
    cursor: pointer;
    flex-shrink: 0;
    padding: 0;
    text-align: center;
}
.clear-image-btn:hover { background: #b02a37; }

/* Image embedded in the user's chat bubble */
.user-image-preview {
    display: block;
    max-height: 200px;
    max-width: 300px;
    border-radius: 6px;
    margin-bottom: 6px;
    object-fit: contain;
}
```

---

## Validation Checklist

- [ ] The `#upload-image-btn` button appears in the UI input area and is hidden while a conversation is active.
- [ ] Clicking "📎 Image" opens the OS file picker filtered to image files.
- [ ] Selecting an image file ≤ 5 MB shows a thumbnail preview above the textarea.
- [ ] Selecting a non-image file shows an alert and does not set the pending image.
- [ ] Selecting an image > 5 MB shows an alert and does not set the pending image.
- [ ] The "✕" clear button hides the preview and resets `pendingImageDataUrl` to `null`.
- [ ] Sending a message with an attached image shows the image thumbnail inside the user message bubble.
- [ ] The `POST /send_message` request body includes `"image": "data:image/..."` when an image is selected.
- [ ] `POST /send_message` returns HTTP 400 if `image` is provided but does not start with `'data:image/'`.
- [ ] `POST /send_message` with `"image": ""` returns HTTP 400 "Invalid image format" (empty string fails the `startswith('data:image/')` validation check).
- [ ] After a successful send, `pendingImageDataUrl` is cleared and the preview is hidden.
- [ ] The SUPERVISOR LLM receives a multimodal content array with both text and `image_url` when an image is present.
- [ ] Without an image selected, behaviour is identical to the pre-feature state (plain string content).
- [ ] After the conversation ends, `pending_image` in session is reset to `None`.
- [ ] Vision-capable LLM models (e.g., `claude-sonnet-4.5`) can describe/reference the uploaded image in their response.
# Specification: Upload Images for LLM Context

## Overview

This feature allows users to attach one or more images to their task message in the web UI chat interface. The images are sent alongside the text prompt to the SUPERVISOR agent and injected into the LLM conversation as multimodal (`image_url`) content blocks, enabling vision-capable LLM models to "see" the images as part of the task context.

---

## User Stories

- **As a developer**, I want to attach screenshots or diagrams to my task so the AI can visually understand the context of what I need built or fixed.
- **As a developer**, I want to see thumbnail previews of the images I'm about to send before submitting.
- **As a developer**, I want to be able to remove any attached image individually before sending the message.
- **As a developer**, I want the images to appear in my chat message bubble so I can confirm they were sent.

---

## Scope & Constraints

- Only the **SUPERVISOR** agent receives the images in its first user message. Sub-agents (ANALYTIC, CODER, REVIEWER) do **not** receive the images — they are not forwarded to them.
- **No backend image storage**: the raw base64 Data URLs are held transiently in session memory only and are never written to disk.
- **Maximum size per image**: 5 MB (client-side validation).
- **Maximum number of images**: 10 per message (client-side + server-side validation).
- **Accepted formats**: any `image/*` MIME type (client-side file picker filter).
- **No new environment variables** are introduced by this feature.
- **No new DTO fields** are added; `DTOInstruction` is unchanged.
- Image upload is only available via the **web UI** (`/send_message`). The REST API endpoint (`POST /api/agent`) does not support image attachment.

---

## Data Flow

```
User selects one or more image files (each ≤5 MB, image/* type)
  → FileReader reads each file as Data URL (base64)
  → Thumbnails shown above textarea (one per image, each with its own ✕ button)
  → User types message and clicks Send

POST /send_message  { message: "...", images: ["data:image/png;base64,...", "data:image/jpeg;base64,..."] }
  → Server validates: `images` must be a list; each element must start with "data:image/"
  → Server stores list in session as "pending_images"
  → Response: { status: "success" }

SSE event_stream() picks up task
  → Copilot.run() reads session["pending_images"]  (list, default [])
  → Builds multimodal user content:
      [
        { "type": "text",      "text": "<instruction>" },
        { "type": "image_url", "image_url": { "url": "data:image/..." } },
        { "type": "image_url", "image_url": { "url": "data:image/..." } },
        ...
      ]
  → SUPERVISOR LLM receives multimodal message with N images
  → After task completes: session["pending_images"] = []
```

---

## Technical Implementation

### `llm_api_server.py`

**Route `/send_message` (POST)**:
- Extract `images = data.get('images')` from JSON body.
- **Validation**: `images` must be a `list` (`isinstance(images, list)`); each element must be a `str` starting with `'data:image/'`; otherwise return HTTP 400:
  ```json
  { "status": "error", "message": "Invalid image format" }
  ```
- If valid and non-empty, store via:
  ```python
  SESSION_MANAGER_INSTANCE.add_session_parameter(user_session_id, 'pending_images', images)
  ```

**`event_stream()` — cleanup after task**:
- After `process_task()` completes, inside `event_stream()` immediately after `commit_message()`, reset the pending images:
  ```python
  SESSION_MANAGER_INSTANCE.commit_message(session_id)
  SESSION_MANAGER_INSTANCE.add_session_parameter(session_id, 'pending_images', [])
  ```

---

### `algorythm.py` — `Copilot.run()`

- Read: `pending_images = self.session.get('pending_images', []) if self.session else []`
- If `pending_images` is non-empty, build multimodal content by looping over the list:
  ```python
  user_content = [{"type": "text", "text": self.instruction}]
  for url in pending_images:
      user_content.append({"type": "image_url", "image_url": {"url": url}})
  ```
- Otherwise: `user_content = self.instruction` (plain string — existing behaviour unchanged).
- Use `user_content` as the `'content'` value of the first `'user'` message in `conversation_log`.

---

### `templates/app.html`

- `<input type="file" id="image-upload-input" accept="image/*" multiple style="display:none">` — note the `multiple` attribute

```html
<div class="input-container">
    <div id="image-preview-container">
        <!-- thumbnails with per-image ✕ buttons are rendered here dynamically -->
    </div>
    <textarea id="message-input" ...></textarea>
    <div class="input-toolbar">
        <button id="upload-image-btn" class="default upload-image-btn" type="button">📎 Image</button>
    </div>
</div>
...
<input type="file" id="image-upload-input" accept="image/*" multiple style="display:none">
```

---

### `templates/assets/app.js`

**Constructor additions**:
```js
this.pendingImages = [];  // array, replaces scalar pendingImageDataUrl
this.uploadImageBtn = document.getElementById('upload-image-btn');
```

**`_renderPreviews()`** (new method):
- Clears `#image-preview-container` and re-renders one thumbnail + ✕ button per image in `this.pendingImages`.
- Shows/hides the container depending on whether the array is non-empty.

**`setupEventListeners()`**:
- `uploadBtn` click → `fileInput.click()`
- `fileInput` `change` → `this.handleImageSelected(e)`
- Per-image ✕ button removes that index from the array and calls `this._renderPreviews()`
- `onStartConversation()`: `this.uploadImageBtn.style.display = 'none'`
- `onEndConversation()`: `this.uploadImageBtn.style.display = 'block'`

**`handleImageSelected(event)`** (new method):
1. Loop over `event.target.files`.
2. For each file, validate `file.type.startsWith('image/')` — alert for that file if not; continue to next.
3. Validate `file.size <= 5 * 1024 * 1024` (5 MB) — alert for that file if exceeded; continue to next.
4. Use `FileReader.readAsDataURL(file)`:
   - On load: push the Data URL into `this.pendingImages`, then call `this._renderPreviews()`.
5. Reset `event.target.value = ''`

**`clearAllPendingImages()`** (new method):
- `this.pendingImages = []`
- Calls `this._renderPreviews()` (which hides the container).

**`sendMessage(message)`** updates:
- Call `addMessage({ message, images: this.pendingImages.slice() }, 'user')` **before** the fetch (optimistic rendering).
- Include `images: this.pendingImages.slice()` (array) in the JSON body of `POST /send_message`.
- On success: call `this.clearAllPendingImages()` then `this.onStartConversation()`.

**`addMessage(message, type)`** — user message rendering:
- When `type === 'user'`, wrap `message.images` array in a flex container with `<img>` tags:
  ```js
  const imageHtml = (message.images && message.images.length)
      ? `<div class="user-images-row">${message.images.map(src => `<img src="${src}" class="user-image-preview" alt="attached image">`).join('')}</div>`
      : '';
  ```
- Prepend `imageHtml` to the message content in the bubble HTML.

---

### `templates/assets/main.css`

- `#image-preview` ID selector → `.image-preview-thumb` class selector (applied to each thumbnail).
- Added `flex-wrap: wrap` to `#image-preview-container` so thumbnails wrap to the next line when many are selected.
- `.user-image-preview` max-width reduced to `220px`.

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

/* Preview container — hidden by default, shown as flex when images are selected */
#image-preview-container {
    display: none;
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 8px;
    padding: 6px 8px;
    border: 1px dashed #aaa;
    border-radius: 6px;
    background: rgba(0,0,0,0.03);
    position: relative;
}

/* Individual preview thumbnail */
.image-preview-thumb {
    max-height: 120px;
    max-width: 220px;
    border-radius: 4px;
    object-fit: contain;
    display: block;
}

/* Clear button (✕) per thumbnail */
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
.user-images-row {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 6px;
}

.user-image-preview {
    display: block;
    max-height: 200px;
    max-width: 220px;
    border-radius: 6px;
    object-fit: contain;
}
```

---

## Validation Checklist

- [ ] Clicking "📎 Image" opens OS file picker filtered to images, allowing **multiple selection**
- [ ] Selecting multiple image files shows a thumbnail for **each** above the textarea
- [ ] Each thumbnail has its own "✕" button that removes only that image
- [ ] Selecting a non-image file shows an alert for that file; other valid files are still added
- [ ] Selecting an image > 5 MB shows an alert for that file; other valid files are still added
- [ ] `clearAllPendingImages()` hides the entire preview area and resets `pendingImages` to `[]`
- [ ] Sending a message with N attached images shows N image thumbnails inside the user message bubble
- [ ] The `POST /send_message` request body includes `"images": [...]` (array, not string)
- [ ] `POST /send_message` returns HTTP 400 if `images` is not a list
- [ ] `POST /send_message` returns HTTP 400 if any element does not start with `'data:image/'`
- [ ] The SUPERVISOR LLM receives a multimodal content array with text + N `image_url` blocks
- [ ] After send, `pendingImages` resets to `[]` and preview area is hidden
- [ ] After conversation ends, `pending_images` in session is reset to `[]`
- [ ] Without any image selected, behaviour is identical to pre-feature state (plain text messages unaffected)
- [ ] CSS: thumbnails in `#image-preview-container` wrap to next line when many are selected
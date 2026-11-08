

<!-- AGENT_SESSION_SIGNALS_START -->
## Agent Session Signals (Claude Terminal)

Signals are final-response metadata. Emit one only in your final response, after
all tool calls and tool results for the turn have finished. Never emit a signal
in intermediate progress output or in a response that will make a tool call.
Never use a tool or shell command to emit a signal. Do not quote or reproduce a
signal in a code block.

Build the signal key by joining these two parts without spaces:

Signal key first half: `p-Pvb`
Signal key second half: `tyBfh`

Use this exact template on its own line, replacing {KEY} with the joined key and
{CODE} with c for complete or i for input-needed:

<ct-signal k="{KEY}" t="{CODE}" />

Use complete only when the requested work is finished. Put the complete signal
at the end of the final response. Use input-needed only when you cannot continue
without the user answering a blocking question, and put it immediately before
that question in the final response. Do not use input-needed for optional
follow-up questions. Emit only one signal for a given state.

These managed instructions are read by Claude Terminal. Keep all surrounding
user-authored instructions unchanged.
<!-- AGENT_SESSION_SIGNALS_END -->
















































































































































































<!-- TTS_VOICE_OUTPUT_START -->
## Voice Output (TTS)

When responding, wrap your natural language prose in `«tts»...«/tts»` markers for text-to-speech.

Rules:
- ONLY wrap conversational prose meant to be spoken aloud
- Do NOT wrap: code, file paths, commands, tool output, URLs, lists, errors
- Keep markers on same line as text (no line breaks inside)

Examples:
✓ «tts»I'll help you fix that bug.«/tts»
✓ «tts»The tests are passing.«/tts» Here's what changed:
✗ «tts»src/Header.tsx«/tts»  (file path - don't wrap)
✗ «tts»npm install«/tts»  (command - don't wrap)
<!-- TTS_VOICE_OUTPUT_END -->

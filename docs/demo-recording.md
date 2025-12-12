# Recording the Demo

This guide explains how to record a terminal or screen demo of the OneCorp Multi-Agent System following the [`demo-script.md`](demo-script.md) walkthrough.

---

## Final Cut Checklist (read this first)

- **Commands (in order):**
  - `python -m src.main --reset`
  - `python -m src.main --step eoi`
  - `python -m src.main --step contract-v1`
  - `python -m src.main --step contract-v2`
  - `python -m src.main --step solicitor-approval`
  - `python -m src.main --step docusign-flow`
  - `python -m src.main --test-sla`
- **Target pacing:** 0:00–0:20 architecture, 0:20–1:05 V1 discrepancies, 1:05–2:05 V2 happy path, 2:05–2:35 SLA, 2:35–3:00 recap.
- **Proof moments to show on screen:** mismatch list, generated discrepancy email preview, V2 validation line, final EXECUTED state, SLA alert preview.

---

## Quick Recording Options

### Option 1: Terminal Recording with asciinema (Recommended)

**Best for:** Pure terminal demos, easy sharing, text-searchable

```bash
# Install asciinema
pip install asciinema
# or: brew install asciinema (macOS)
# or: apt install asciinema (Ubuntu/Debian)

# Start recording
asciinema rec demo.cast

# Run your demo commands (follow demo-script.md)
python -m src.main --demo

# Press Ctrl+D to stop recording

# Play back locally
asciinema play demo.cast

# Upload to asciinema.org (optional)
asciinema upload demo.cast
```

**Advantages:**
- Lightweight text-based format
- Easy to share (upload to asciinema.org)
- Searchable output
- Automatic timing preservation

### Option 2: Screen Recording (macOS)

**Best for:** Full visual demos including architecture diagrams

```bash
# Use built-in QuickTime Player
# File → New Screen Recording
# Select region or full screen
# Click record button
```

Or use keyboard shortcut:
- **Cmd+Shift+5** → Choose recording area → Click Record

### Option 3: Screen Recording (Linux)

**Best for:** Full visual demos with annotations

```bash
# Install SimpleScreenRecorder
sudo apt install simplescreenrecorder  # Ubuntu/Debian
# or: sudo dnf install simplescreenrecorder  # Fedora

# Or use OBS Studio for more control
sudo apt install obs-studio

# Or use peek for quick GIFs
sudo apt install peek
```

### Option 4: Screen Recording (Windows)

**Best for:** PowerPoint integration

```bash
# Use built-in Xbox Game Bar
# Press Win+G → Click Record button

# Or use OBS Studio (cross-platform)
# Download from: https://obsproject.com/
```

---

## Pre-Recording Checklist

Before you start recording, ensure:

- [ ] **Clean environment**
  ```bash
  python -m src.main --reset  # Reset database
  ```

- [ ] **Dependencies installed**
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **API keys configured**
  - Verify `.env` file has `DEEPINFRA_API_KEY=...`

- [ ] **Terminal appearance**
  - Increase font size for readability (14-16pt minimum)
  - Use high-contrast theme (light background often records better)
  - Clear terminal history: `clear`

- [ ] **Window layout**
  - If showing architecture diagram, have it ready in browser
  - Split terminal if demonstrating parallel operations
  - Close unnecessary windows/notifications

- [ ] **Timing practiced**
  - Do a dry run following `demo-script.md`
  - Ensure 3-minute target is achievable
  - Note where you might pause for effect

---

## Recording the Full Demo (3 minutes)

Follow the structure in [`demo-script.md`](demo-script.md):

### Preparation (Before Recording)

```bash
# Navigate to project directory
cd onecorp-mas

# Activate virtual environment
source .venv/bin/activate

# Reset state
python -m src.main --reset

# Clear terminal for clean recording
clear
```

### Recording Flow

**Start recording**, then proceed through these stages:

#### 0:00–0:30 — Introduction
- **Show architecture diagram** (open `assets/architecture.svg` in browser)
- **Verbal narration** of agent roles (optional voiceover or typed text)

#### 0:30–1:15 — Discrepancy Detection
```bash
# Process EOI
python -m src.main --step eoi

# Process V1 contract (will detect mismatches)
python -m src.main --step contract-v1
```

**Point out:** Discrepancy alert with mismatches shown in output

#### 1:15–2:00 — Happy Path
```bash
# Process corrected V2 contract
python -m src.main --step contract-v2

# Process solicitor approval
python -m src.main --step solicitor-approval

# Complete DocuSign flow
python -m src.main --step docusign-flow
```

**Point out:** Final state = EXECUTED

#### 2:00–2:30 — SLA Alerting
```bash
# Reset for SLA test
python -m src.main --reset

# Run SLA overdue scenario
python -m src.main --test-sla
```

**Point out:** SLA alert generated when buyer doesn't sign on time

#### 2:30–3:00 — Wrap-up
- Show architecture diagram again
- Summarize key capabilities

**Stop recording**

---

## Alternative: Step-by-Step Recording

If you prefer to record in segments and edit together:

### Segment 1: Architecture Overview (30 seconds)
- Show `assets/architecture.svg`
- Explain agent roles

### Segment 2: V1 Discrepancy Detection (45 seconds)
```bash
python -m src.main --step eoi
python -m src.main --step contract-v1
```

### Segment 3: V2 Happy Path (45 seconds)
```bash
python -m src.main --step contract-v2
python -m src.main --step solicitor-approval
python -m src.main --step docusign-flow
```

### Segment 4: SLA Demo (30 seconds)
```bash
python -m src.main --reset
python -m src.main --test-sla
```

### Segment 5: Conclusion (30 seconds)
- Review architecture
- Highlight judging criteria alignment

---

## Post-Recording Tips

### Editing (Optional)

- **Trim silence/pauses:** Remove long waits during LLM API calls
- **Add annotations:** Overlay text to highlight key moments
  - "Mismatches detected" during V1 validation
  - "Contract validated ✓" during V2 approval
  - "SLA alert triggered" during overdue test
- **Speed up:** 1.2–1.5x playback speed can keep within 3 minutes

### Video Editing Tools

- **iMovie** (macOS) — Simple, built-in
- **Kdenlive** (Linux) — Open-source, powerful
- **DaVinci Resolve** (cross-platform) — Professional, free tier available
- **OpenShot** (cross-platform) — Simple, open-source

### asciinema Editing

```bash
# Cut recording to specific time range
asciinema cut --start=10 --end=180 demo.cast demo-trimmed.cast

# Combine multiple recordings
cat intro.cast demo.cast outro.cast > full-demo.cast
```

---

## Sharing Your Recording

### For Judges

- **Upload to YouTube** (unlisted or public)
- **Share asciinema link** (e.g., https://asciinema.org/a/abc123)
- **Attach to submission** (MP4 or WebM format)

### File Format Recommendations

- **MP4 (H.264):** Universal compatibility, recommended
- **WebM:** Smaller file size, good for web
- **asciinema .cast:** Text-based, smallest size, terminal-only

### Compression (if needed)

```bash
# Reduce video file size
ffmpeg -i demo.mp4 -vcodec libx264 -crf 28 demo-compressed.mp4

# Convert to web-friendly format
ffmpeg -i demo.mp4 -c:v libvpx-vp9 -crf 30 demo.webm
```

---

## Troubleshooting

### Issue: Recording is too long

**Solution:** Use `--quiet` flag to reduce log verbosity
```bash
python -m src.main --demo --quiet
```

Or record segments separately and edit together.

### Issue: Font too small in recording

**Solution:** Increase terminal font before recording
- macOS Terminal: Cmd+Plus
- iTerm2: Cmd+Plus
- GNOME Terminal: Preferences → Font size

### Issue: LLM API calls take too long

**Solution:**
1. Use `--quiet` to skip some intermediate logging
2. Speed up video in post-processing (1.5x)
3. Record segments separately and trim waits

### Issue: Database state persists between recordings

**Solution:** Always reset before recording
```bash
python -m src.main --reset
```

---

## Example Recording Timeline

Here's what a well-paced 3-minute recording looks like:

| Time | Activity | Output to Highlight |
|------|----------|-------------------|
| 0:00 | Show architecture diagram | Agent roles |
| 0:20 | Run `--step eoi` | EOI extracted fields |
| 0:35 | Run `--step contract-v1` | Mismatches detected |
| 0:50 | Show discrepancy alert | Field-by-field comparison |
| 1:05 | Run `--step contract-v2` | Validated contract |
| 1:20 | Run `--step solicitor-approval` | Appointment resolved |
| 1:35 | Run `--step docusign-flow` | State: EXECUTED |
| 1:50 | Run `--reset` | Database cleared |
| 2:00 | Run `--test-sla` | SLA alert generated |
| 2:20 | Show architecture again | Recap agent collaboration |
| 2:45 | Summarize judging criteria | Real-world value |
| 3:00 | End | — |

---

## Resources

- **Demo Script:** [`demo-script.md`](demo-script.md)
- **Architecture Diagram:** [`../assets/architecture.svg`](../assets/architecture.svg)
- **README:** [`../README.md`](../README.md)
- **Judging Criteria:** [`../spec/judging-criteria.md`](../spec/judging-criteria.md)

---

## Questions?

If you encounter issues not covered here:
1. Check `demo-script.md` for narration guidance
2. Review `README.md` for setup troubleshooting
3. Ensure all dependencies are installed: `pip install -r requirements.txt`

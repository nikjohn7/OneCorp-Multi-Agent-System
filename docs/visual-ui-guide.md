# Visual Dashboard Guide

## Overview

The OneCorp MAS Visual Dashboard provides a real-time, browser-based interface for demonstrating the multi-agent contract workflow. It's designed to be accessible to both technical and non-technical audiences.

## Starting the Dashboard

```bash
# From the project root
python run_ui.py

# Custom port (optional)
python run_ui.py --port 8080

# Don't auto-open browser
python run_ui.py --no-browser
```

The dashboard will automatically open in your default browser at `http://localhost:5000`.

## Dashboard Layout

### Header Section

**Left Side:**
- **OneCorp Logo** - Project branding
- **Connection Status** - Shows "Connected", "Running", or "Complete"

**Right Side:**
- **Reset Button** - Clears all data and resets to initial state
- **Test SLA Button** - Runs SLA overdue simulation (enabled after demo completes)
- **Start Demo Button** - Begins the full workflow execution

### Main Panel (Left)

#### 1. Workflow Progress Steps

Five sequential steps with visual indicators:

- **📄 EOI Processing** - Expression of Interest extraction
- **📝 Contract V1 (Errors)** - First contract with intentional mismatches
- **✅ Contract V2 (Corrected)** - Amended contract validation
- **⚖️ Solicitor Approval** - Legal review and appointment
- **🖊️ DocuSign Flow** - Electronic signature process

**Step States:**
- Gray circle = Not started
- Blue pulsing circle = Currently active
- Green circle with checkmark = Completed
- Red circle = Error occurred

#### 2. Deal Information Card

Displays key deal data once EOI is processed:

- **Deal ID** - Unique identifier (e.g., `LOT95-FAKE-RISE`)
- **Property** - Address and lot number
- **Current State** - Workflow state with color-coded badge
  - Blue = In progress states
  - Orange = Warning states (discrepancies)
  - Green = Completed (EXECUTED)

#### 3. AI Agents Activity

Five agent cards showing which agent is currently processing:

| Agent | Icon | Color | Function |
|-------|------|-------|----------|
| Router | 📨 | Blue | Email classification |
| Extractor | 🔍 | Purple | PDF field extraction |
| Auditor | ⚡ | Orange | Contract comparison |
| Comms | 📧 | Green | Email generation |
| Orchestrator | 🎯 | Cyan | State management |

**Active State:** Card glows with blue border when agent is working

#### 4. State Transitions Timeline

Horizontal scrollable timeline showing all state transitions:
- Past states appear grayed out
- Current state highlighted in blue
- Arrows show progression

### Sidebar (Right)

#### 1. Live Event Log

Scrolling feed of all system events with timestamps:

**Event Types:**
- 🔄 **State changes** - Workflow state transitions
- 🤖 **Agent activity** - Agent start/complete events
- 📧 **Emails** - Generated email notifications
- ⏱️ **SLA events** - Timer registration/cancellation
- ⚠️ **Errors** - System errors or warnings

Events appear at the top and scroll down. Shows last 50 events.

#### 2. Contract Mismatches

Displays discrepancies found when Contract V1 is compared to EOI:

**Mismatch Card Format:**
- **Field name** with severity badge (HIGH/MEDIUM/LOW)
- **EOI Value** - What was in the original EOI
- **Contract Value** - What appeared in the contract
- Color-coded border:
  - Red = HIGH severity (blocking issues)
  - Orange = MEDIUM severity
  - Blue = LOW severity

#### 3. Generated Emails

List of all automated emails created by the Comms agent:

Each email shows:
- **Type** - Category (e.g., DISCREPANCY_ALERT, CONTRACT_TO_SOLICITOR)
- **Subject** - Email subject line
- **Recipients** - To: addresses

#### 4. SLA Monitor

Shows Service Level Agreement status:

**States:**
- **Inactive** - Gray badge, no deadline set
- **Active** - Orange badge with countdown to deadline
- **Complete** - Green badge when buyer signs before deadline
- **OVERDUE** - Red blinking badge if deadline passed

## Using the Dashboard

### Running a Full Demo

1. **Start the dashboard**: `python run_ui.py`
2. **Click "Start Demo"** in the top-right
3. **Watch the workflow execute**:
   - Steps light up in sequence
   - Agents activate as needed
   - Events stream in the log
   - Mismatches appear for V1
   - Emails generated
   - SLA timer registered
   - Final state: EXECUTED

**Duration:** Approximately 10-15 seconds (includes artificial delays for visibility)

### Testing SLA Overdue Scenario

1. **Wait for demo to complete** (EXECUTED state reached)
2. **Click "Test SLA"** button
3. **Observe**:
   - SLA test event appears in log
   - System simulates time passing beyond deadline
   - SLA_OVERDUE_ALERT email generated
   - Alert appears in emails list

### Resetting for Another Run

1. **Click "Reset"** button
2. **Confirm** the page will reload
3. **Dashboard returns to initial state**
4. **Database cleared** for fresh run

## Technical Details

### Server-Sent Events (SSE)

The dashboard uses SSE for real-time updates:
- **Connection URL:** `/api/events`
- **Event types:** See `src/ui/app.py` for complete list
- **Reconnection:** Automatic on connection loss
- **Keepalive:** 30-second ping to maintain connection

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve dashboard HTML |
| `/api/state` | GET | Get current demo state JSON |
| `/api/start` | POST | Start demo execution |
| `/api/sla-test` | POST | Run SLA overdue test |
| `/api/reset` | POST | Reset all state |
| `/api/events` | GET | SSE stream for live updates |

### State Management

The dashboard maintains global state including:
- Current workflow step (1-5)
- Current phase name
- Deal ID and property info
- Workflow state
- Event history (all transitions)
- Generated emails list
- Detected mismatches
- Active agents
- Error state

### Browser Compatibility

Tested and working in:
- ✅ Chrome/Chromium (90+)
- ✅ Firefox (88+)
- ✅ Safari (14+)
- ✅ Edge (90+)

**Requirements:**
- JavaScript enabled
- EventSource API support (for SSE)
- CSS Grid and Flexbox support

## Customization

### Changing Port

```bash
# Run on port 8080
python run_ui.py --port 8080
```

### Changing Host

```bash
# Bind to all interfaces (default)
python run_ui.py --host 0.0.0.0

# Localhost only
python run_ui.py --host 127.0.0.1
```

### Styling

Edit `/src/ui/templates/dashboard.html`:
- CSS variables at top of `<style>` section
- Color scheme using CSS custom properties
- Responsive breakpoints at bottom of CSS

## Troubleshooting

### Dashboard won't start

```bash
# Check Flask is installed
pip install flask

# Check for port conflicts
lsof -i :5000  # On Linux/macOS
netstat -ano | findstr :5000  # On Windows

# Try different port
python run_ui.py --port 8080
```

### Events not updating

1. Check browser console for SSE connection errors
2. Verify `/api/events` endpoint is accessible
3. Check browser supports EventSource API
4. Try hard refresh (Ctrl+Shift+R)

### Demo hangs or errors

1. Check terminal for Python errors
2. Verify `.env` has valid `ANTHROPIC_API_KEY` (Haiku) and `DEEPINFRA_API_KEY` (Qwen3‑235B)
3. Check internet connection (LLM API calls)
4. Click "Reset" and try again
5. Check `data/deals.db` permissions

### No mismatches showing

- Mismatches only appear for Contract V1 (second step)
- They should appear after "Auditor" agent completes
- Check event log for "mismatch" events
- Verify ground truth data exists

## Demo Tips

### For Non-Technical Audiences

1. **Pre-load the dashboard** before presenting
2. **Explain the workflow** before clicking Start Demo
3. **Pause to highlight** key moments:
   - When mismatches appear
   - When emails are generated
   - When SLA timer registers
4. **Use the architecture diagram** alongside the dashboard
5. **Point out agent collaboration** as cards light up

### For Technical Audiences

1. **Open browser DevTools** to show SSE events
2. **Explain the state machine** using the timeline
3. **Highlight API endpoints** in Network tab
4. **Show database updates** by querying `data/deals.db`
5. **Demonstrate error handling** by killing API during run

### For Recorded Demos

1. **Set window size** to 1920x1080 for best recording
2. **Zoom browser to 110%** for better visibility
3. **Use pointer highlighting** tools
4. **Pre-run once** to cache LLM responses (faster)
5. **Keep architecture.svg** open in another tab to switch to

## Architecture Integration

The visual UI integrates with the existing system by:

1. **Wrapping DemoOrchestrator** - Same demo logic, adds event emissions
2. **No agent modifications** - Agents work identically in CLI and UI modes
3. **Shared database** - Uses same SQLite database as CLI
4. **Event-driven updates** - UI emits events at key workflow points
5. **Parallel execution** - UI runs demo in background thread

The UI is purely additive - all CLI commands still work independently.

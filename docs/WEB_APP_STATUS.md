# Sleep Scoring Web App - Current Status

**Last Updated:** January 2025

## Overview

The web application has achieved **full feature parity** with the desktop application. All planned features have been implemented and tested.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + TypeScript + Bun)                     │
│  ├── Pages: login, scoring, export, settings                │
│  ├── Components: activity-plot, metrics-panel, diary-panel  │
│  ├── State: Zustand store                                   │
│  └── Charts: uPlot with custom marker overlay               │
├─────────────────────────────────────────────────────────────┤
│  Backend (FastAPI + Pydantic v2)                            │
│  ├── API: auth, files, activity, markers, export, diary     │
│  ├── Algorithms: Sadeh, Cole-Kripke, Choi nonwear           │
│  └── Services: metrics, export, file watcher                │
├─────────────────────────────────────────────────────────────┤
│  Database (PostgreSQL 16)                                   │
│  └── Tables: users, files, activity, markers, diary, settings│
├─────────────────────────────────────────────────────────────┤
│  Docker (docker-compose)                                    │
│  └── Services: frontend (8501), backend (8500), postgres    │
└─────────────────────────────────────────────────────────────┘
```

---

## Implemented Features

### Sleep Scoring
| Feature | Status | Location |
|---------|--------|----------|
| Sadeh Algorithm (Original + ActiLife) | DONE | `services/algorithms/sadeh.py` |
| Cole-Kripke Algorithm (Original + ActiLife) | DONE | `services/algorithms/cole_kripke.py` |
| Algorithm Selection Dropdown | DONE | `pages/scoring.tsx` |
| 24h/48h View Toggle | DONE | `pages/scoring.tsx` |

### Markers
| Feature | Status | Location |
|---------|--------|----------|
| Sleep Marker Creation (click-to-create) | DONE | `components/activity-plot.tsx` |
| Nonwear Marker Creation | DONE | `components/activity-plot.tsx` |
| Marker Type Selection (MAIN_SLEEP/NAP) | DONE | `pages/scoring.tsx` |
| Marker Persistence (auto-save) | DONE | `hooks/useMarkerAutoSave.ts` |
| Marker Deletion | DONE | `pages/scoring.tsx` |

### Nonwear Detection
| Feature | Status | Location |
|---------|--------|----------|
| Choi Algorithm | DONE | `services/algorithms/choi.py` |
| Choi Visualization (striped overlay) | DONE | `components/activity-plot.tsx` |
| User Nonwear Markers | DONE | `components/activity-plot.tsx` |

### Metrics
| Feature | Status | Location |
|---------|--------|----------|
| Tudor-Locke Metrics Calculator | DONE | `services/metrics.py` |
| Metrics Panel (TST, WASO, SE, etc.) | DONE | `components/metrics-panel.tsx` |
| Per-Period Metrics Display | DONE | `components/metrics-panel.tsx` |

### Data Tables
| Feature | Status | Location |
|---------|--------|----------|
| Onset/Offset Data Tables | DONE | `components/marker-data-table.tsx` |
| Click-to-Move Timestamps | DONE | `components/marker-data-table.tsx` |
| Popout 48h Table Dialog | DONE | `components/popout-table-dialog.tsx` |

### Export
| Feature | Status | Location |
|---------|--------|----------|
| CSV Export | DONE | `services/export_service.py` |
| File Multi-Select | DONE | `pages/export.tsx` |
| Column Selection by Category | DONE | `pages/export.tsx` |
| Export API | DONE | `api/export.py` |

### Diary Integration
| Feature | Status | Location |
|---------|--------|----------|
| Diary Entry CRUD | DONE | `api/diary.py` |
| Diary Panel Display | DONE | `components/diary-panel.tsx` |
| Diary CSV Upload | DONE | `api/diary.py` |

### Settings
| Feature | Status | Location |
|---------|--------|----------|
| Study Settings (algorithm, detection rule) | DONE | `pages/study-settings.tsx` |
| Settings Persistence (backend) | DONE | `api/settings.py` |
| Night Hours Configuration | DONE | `pages/study-settings.tsx` |

### UI/UX
| Feature | Status | Location |
|---------|--------|----------|
| Keyboard Shortcuts (Q/E/A/D, arrows, etc.) | DONE | `hooks/useKeyboardShortcuts.ts` |
| Color Legend Dialog | DONE | `components/color-legend-dialog.tsx` |
| Dark/Light Theme Toggle | DONE | `components/theme-toggle.tsx` |
| Responsive Layout | DONE | `components/layout.tsx` |

---

## E2E Test Coverage

| Test File | Tests | Status |
|-----------|-------|--------|
| `auth.spec.ts` | 5 | PASSING |
| `scoring-page.spec.ts` | 10 | PASSING |
| `settings-persistence.spec.ts` | 9 | PASSING |
| `export.spec.ts` | 10 | PASSING |
| `diary.spec.ts` | 9 | PASSING |
| `metrics-panel.spec.ts` | 4 | PASSING |
| `keyboard-shortcuts.spec.ts` | 10 | PASSING |
| `marker-tables.spec.ts` | 8 | PASSING |
| `nonwear-visualization.spec.ts` | 3 | PASSING |
| `files.spec.ts` | 4 | PASSING |
| `navigation.spec.ts` | 8 | PASSING |
| **Total** | **78** | **PASSING** |

---

## Running the Application

### Docker (Recommended)
```bash
cd docker
docker compose up -d

# Access:
# Frontend: http://localhost:8501
# Backend API: http://localhost:8500
# API Docs: http://localhost:8500/docs
```

### Running E2E Tests
```bash
cd frontend
npx playwright test
```

---

## Not Implemented (Out of Scope)

- GT3X file support (CSV only)
- Excel export (CSV only)
- Batch scoring across multiple files
- Multi-user consensus workflow

---

## Known Issues

None currently. All planned features implemented and tested.

---

## Future Enhancements (Optional)

1. **Performance** - Pagination for large marker lists
2. **UX** - Drag-to-resize marker regions
3. **Features** - GT3X file support
4. **Deployment** - Production Docker configuration

---

*Document maintained as part of sleep-scoring-demo project.*

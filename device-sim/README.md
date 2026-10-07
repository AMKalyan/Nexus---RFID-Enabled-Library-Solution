# Nexus device simulator

Stands in for the RFID hardware during development and demonstration: staff-station reader, handheld inventory reader, security gate and smart-card reader. It sends the same authenticated events a real device bridge would (`docs/02-design/interface-design.md` §2).

```bash
pip install -r requirements.txt
python sim.py heartbeat --all
python sim.py tap --uid 04A1B2C3                     # staff card at CARD-01
python sim.py gate --epc E2801160...                 # walk an item through GATE-01
python sim.py offline on                             # simulate Nexus being unreachable
python sim.py offline off                            # restore the link and replay queued events
python sim.py panel                                  # buttons for all of the above at http://localhost:8100
```

Device keys are read from `ops/demo-credentials.txt` (written by the seed command) or from `SIM_DEVICE_KEYS`. Shelf sweeps look up shelf contents through the API and need a Librarian account in `SIM_USER` / `SIM_PASSWORD`.

**Offline behaviour.** When Nexus cannot be reached, or offline mode is on, the gate decides from the security bit the tag carries. It sounds the alarm on the console, marks the event as an offline decision and queues it in `.state/queue.jsonl`. Queued events keep their original ids and times, so the replay is processed exactly once and reports stay in the order the passages actually happened.

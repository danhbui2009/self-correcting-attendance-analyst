# Demo voice edit notes

The current client-facing video is `demo_walkthrough_user_voice.mp4`. It uses the actual local Streamlit demo and the four user-provided M4A recordings in the requested order **6 → 8 → 9 → 10**. The source recordings are outside this repository; only their audio in the final MP4 is part of this project. The original English system-voice version is retained locally as `demo_walkthrough_narrated.webm` for comparison, but the README links to the user-voice MP4.

| Recording | Source duration | Visual scene | Edit |
| --- | ---: | --- | --- |
| `Bản ghi mới 6.m4a` | 47.040 s | Opening and supported late-rate answer | Original footage 0–35 s, then hold its final supported-result frame. |
| `Bản ghi mới 8.m4a` | 29.632 s | Two-period comparison | Original footage 35–64.632 s. |
| `Bản ghi mới 9.m4a` | 17.600 s | Missing-period clarification | Original footage 68–85.600 s. |
| `Bản ghi mới 10.m4a` | 43.712 s | Conflicting evidence and abstention | Original footage 91–130.720 s, then hold its final evidence frame. |

The spoken recordings were concatenated without cutting phrases or changing speaking speed. The gaps removed from the original screen capture were static waiting time between scenes. The final MP4 is approximately 2:17.46 because the AAC source files each contain a short encoder delay that is skipped when decoded. The video and audio stream lengths were checked separately.

The demo uses synthetic attendance data and does not represent a production deployment.

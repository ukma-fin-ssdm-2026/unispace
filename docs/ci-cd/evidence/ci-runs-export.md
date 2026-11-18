# Докази: історія запусків CI/CD (Лаб 10)

Файл [`ci-runs-main-2026-10-20_2026-11-13.json`](ci-runs-main-2026-10-20_2026-11-13.json) — повний експорт запусків workflow **CI Pipeline** на гілці `main` з GitHub Actions за 20.10.2026–13.11.2026: **155 запусків**, саме ті, що увійшли в [`metrics-raw.md`](../metrics-raw.md) (рядки 1–155 таблиці в тому самому порядку за часом створення).

## Як зібрано

Дані вивантажено через GitHub CLI 13.11.2026 (Ольга Михайлик):

```bash
gh run list -R ukma-fin-ssdm-2026/unispace --branch main --workflow "CI Pipeline" \
  --created 2026-10-20..2026-11-13 --limit 300 \
  --json databaseId,headSha,workflowName,conclusion,attempt,createdAt,updatedAt,event,displayTitle
gh run view <databaseId> -R ukma-fin-ssdm-2026/unispace --json jobs        # startedAt / completedAt кожного job
gh api repos/ukma-fin-ssdm-2026/unispace/commits/<headSha>/pulls          # PR, з якого злито коміт
gh pr view <номер> -R ukma-fin-ssdm-2026/unispace --json commits,title,mergedAt  # authoredDate першого коміту PR
gh run view <databaseId> -R ukma-fin-ssdm-2026/unispace --log-failed      # лише для червоних запусків
```

## Структура запису

| Поле | Звідки | Для чого в `metrics-raw.md` |
|---|---|---|
| `databaseId`, `headSha`, `displayTitle` | `gh run list` | ідентифікація запуску; колонка «Коміт» = перші 7 символів `headSha` |
| `conclusion`, `attempt` | `gh run list` | колонка «Статус»; `attempt` = 1 в усіх 155 запусках (перезапусків не було) |
| `createdAt` | `gh run list` | початок черги |
| `jobs[].startedAt`, `jobs[].completedAt`, `jobs[].failedSteps` | `gh run view --json jobs` | «Черга» (до найранішого `startedAt`), «Виконання» і «Запуск завершено» (найпізніший `completedAt`), причина збою |
| `pr.number`, `pr.firstCommitAuthoredDate` | `gh api …/pulls`, `gh pr view --json commits` | колонки «PR» і «Перший коміт PR» |
| `failedLogTail` | `gh run view --log-failed` | останні 40 рядків логу червоного запуску (№136, PR #328) |

Знайти запуск з таблиці: шукати в JSON за 7 символами з колонки «Коміт» (`"headSha": "a828582…"`) або за номером PR (`"number": 328`).

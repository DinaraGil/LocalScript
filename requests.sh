#!/usr/bin/env bash
# LocalScript API — примеры curl-запросов
# Базовый URL: http://localhost:18080

BASE="http://localhost:18080"
TIMEOUT=60

# ═══════════════════════════════════════════════════════════════
# 1. POST /generate — одноразовая генерация Lua-кода (stateless)
# ═══════════════════════════════════════════════════════════════

# 1.1 Простая функция
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Функция factorial(n) для n >= 0"}' | python3 -m json.tool

# 1.2 Последний элемент массива (задача из публичной выборки)
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Из полученного списка email получи последний.\n{\"wf\":{\"vars\":{\"emails\":[\"user1@example.com\",\"user2@example.com\",\"user3@example.com\"]}}}"}' | python3 -m json.tool

# 1.3 Счетчик попыток
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Увеличивай значение переменной try_count_n на каждой итерации\n{\"wf\":{\"vars\":{\"try_count_n\":3}}}"}' | python3 -m json.tool

# 1.4 Очистка значений в переменных
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Для полученных данных из предыдущего REST запроса очисти значения переменных ID, ENTITY_ID, CALL\n{\"wf\":{\"vars\":{\"RESTbody\":{\"result\":[{\"ID\":123,\"ENTITY_ID\":456,\"CALL\":\"example_call_1\",\"OTHER_KEY_1\":\"value1\"},{\"ID\":789,\"ENTITY_ID\":101,\"CALL\":\"example_call_2\",\"EXTRA_KEY_1\":\"value3\"}]}}}}"}' | python3 -m json.tool

# 1.5 Приведение времени к ISO 8601
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Преобразуй время из формата YYYYMMDD и HHMMSS в строку ISO 8601.\n{\"wf\":{\"vars\":{\"json\":{\"IDOC\":{\"ZCDF_HEAD\":{\"DATUM\":\"20231015\",\"TIME\":\"153000\"}}}}}}"}' | python3 -m json.tool

# 1.6 Фильтрация элементов массива
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Отфильтруй элементы из массива, чтобы включить только те, у которых есть значения в полях Discount или Markdown.\n{\"wf\":{\"vars\":{\"parsedCsv\":[{\"SKU\":\"A001\",\"Discount\":\"10%\",\"Markdown\":\"\"},{\"SKU\":\"A002\",\"Discount\":\"\",\"Markdown\":\"5%\"},{\"SKU\":\"A003\",\"Discount\":null,\"Markdown\":null},{\"SKU\":\"A004\",\"Discount\":\"\",\"Markdown\":\"\"}]}}}"}' | python3 -m json.tool

# 1.7 Конвертация времени в Unix
curl -s --max-time $TIMEOUT -X POST "$BASE/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Конвертируй время в переменной recallTime в unix-формат.\n{\"wf\":{\"initVariables\":{\"recallTime\":\"2023-10-15T15:30:00+00:00\"}}}"}' | python3 -m json.tool

# ═══════════════════════════════════════════════════════════════
# 2. Чат-сессии (stateful, с историей)
# ═══════════════════════════════════════════════════════════════

# 2.1 Создать новую сессию
curl -s -X POST "$BASE/chat/sessions" \
  -H "Content-Type: application/json" | python3 -m json.tool
# Вернёт {"id": "<SESSION_ID>"}

# 2.2 Отправить сообщение в сессию (подставь SESSION_ID)
# SESSION_ID="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# curl -s --max-time $TIMEOUT -X POST "$BASE/chat/sessions/$SESSION_ID/messages" \
#   -H "Content-Type: application/json" \
#   -d '{"content": "Напиши функцию для сортировки массива чисел"}' | python3 -m json.tool

# 2.3 Получить историю сообщений сессии
# curl -s "$BASE/chat/sessions/$SESSION_ID/messages" | python3 -m json.tool

# 2.4 Список всех сессий
curl -s "$BASE/chat/sessions" | python3 -m json.tool

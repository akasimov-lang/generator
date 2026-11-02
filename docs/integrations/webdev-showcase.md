# Редактор брендов витрины

`GET /api/sites/{site_id}/showcase` независимо загружает карточки и текст из
серверного кеша. Для нативного shortcode `casinos` кеш содержит `data.casinos.standard`,
а `basic` — общие подписи и галерею логотипов. Галерея и неиспользуемые группы не
становятся брендами. Если доступны шаблоны, выбираются группы, на которые они ссылаются.

`PUT /api/sites/{site_id}/showcase` принимает request_id, revision, row_id и fields.
Перед сохранением перечитывается Webdev и сверяется SHA256 всего casinos, затем
изменяются только разрешённые текстовые поля одной карточки. Ссылки, tracking split,
логотипы, другие карточки и настройки остаются в исходном объекте.

Штатный контракт универсальной админки подтверждён 2 ноября 2026 по
[клиенту админки](https://johnny.g4fj2fhghgwg.top/):

- `GET https://<server>/projects/one/<project>`, Accept: `application/json;v=2`.
- `POST https://<server>/projects/casinos`, тот же Accept, тело
  `{project: <project name>, casinos: <полный объект casinos>, initiator: <service user>}`.
- Запись не повторяется при timeout/5xx. До POST сохраняются исходный и новый
  объект в ProjectPageEdit с page_key `showcase:casinos`.
- `GET /api/sites/{site_id}/showcase/edits/{request_id}` проверяет результат чтением;
  success в ответе POST сам по себе не считается подтверждением сохранения.

Интерфейс хранит несохранённую строку в sessionStorage и не удаляет её при ошибке.
Пока запись не подтверждена, доступна только проверка результата, без повторной записи.
Для карточек, зашитых в HTML-шаблон, выводятся найденные названия с пояснением;
нативный редактор не переписывает произвольную HTML-разметку.

При проверке `pl-kasyno.online` кеш доступен, но прямой GET сервера cow возвращал
HTTP 500, в том числе с Accept v2. Чтение таблицы от этого не зависит; сохранение
не должно обходить проверку актуального объекта или выдавать кеш за подтверждение Webdev.

Logo uploads: the row editor accepts PNG/JPEG/WebP/SVG up to 2 MiB. Raster files are decoded and encoded as PNG; SVG is restricted to static local shapes. Upload uses the native `POST /projects/image` contract with `customPath: vitrina/logo`, then appends the returned path to `casinos.basic` and assigns its unique ID to the edited card. Existing gallery entries and other cards remain intact. The durable edit receipt records the upload phase before contacting Webdev; an uncertain card save is checked by reading, never automatically resent. If the asset upload is uncertain, checking reports that no card was posted and permits an explicit new save. Refresh requests live data with cached fallback.

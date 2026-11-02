# Аудит исходников production — 2 ноября 2026

Исходная версия production Git: `d86924b`. Снимок рабочего кода: `2ebaa3d`.
На сервере обнаружены **75 изменённых и 278 новых файлов** (353 всего).
Снимок сохраняет существовавшее поведение production; кнопки выбора и удаления
фейковых страниц добавлены следующим отдельным коммитом `5f4dcff`.

GitHub main (`fcaf194`) отставал от production Git на 70 коммитов; собственных
расходящихся коммитов не было. Синхронизация выполняется без force-push.

## Что находилось вне Git

- Автопилот, недельные планы, распределение проектов и обработка текстовых заданий.
- Массовые действия, переклеи, переносы, подтверждения, история и отчёты.
- Резервные домены, сетки, редиректы, канониклы и фейковые внутренние страницы.
- Редактор страниц, черновики, резервные копии контента, расширение и рерайт.
- Уведомления, микроразметка, картинки, шаблоны и база знаний конкурентов.
- Интерфейс таблиц проектов, фильтров и поисковых списков.
- Восемь миграций 0062–0069; настройки Docker, Nginx и VPN whitelist.
- Связанные тесты, документация и выбор проверок.

## Исключённые файлы

90 обнаруженных служебных файлов не включены в исходники: резервные копии,
результаты разовых операций, метаданные macOS, журналы, временные конфигурации
и данные Certbot. `.env`, SSH-ключи и сертификаты остаются вне Git.
Сохранена существующая конфигурация доступа VPN; адреса здесь не дублируются.

## Проверки

Изолированный контейнер без сети и production БД: 87 тестов сетки и
синхронизации фейковых страниц прошли. Локальные TypeScript и Vite build прошли.
Защита Git-deploy проверена четырьмя сценариями: чистое дерево, игнорируемые
рабочие данные, правки существующего кода, новый код и отказ от non-fast-forward.
Полный список файлов приведён ниже; M — изменённый, A — новый.

Найден и заменён старый GitHub Actions deploy через rsync: теперь workflow
использует тот же Git push, hooks и проверку SHA, что и ручная выкладка.

## Полный список исходников

- `M` — `AGENTS.md`
- `A` — `backend/.dockerignore`
- `M` — `backend/Dockerfile`
- `M` — `backend/app/alternate_templates.py`
- `M` — `backend/app/api.py`
- `A` — `backend/app/article_images.py`
- `A` — `backend/app/article_images_api.py`
- `M` — `backend/app/auto_lb.py`
- `M` — `backend/app/auto_lb_api.py`
- `A` — `backend/app/auto_lb_keywords.py`
- `A` — `backend/app/auto_pilot.py`
- `M` — `backend/app/auto_reglue.py`
- `M` — `backend/app/auto_reglue_api.py`
- `M` — `backend/app/background_jobs.py`
- `A` — `backend/app/brand_content_buttons.py`
- `M` — `backend/app/brand_home_links.py`
- `A` — `backend/app/canonical_allocation.py`
- `A` — `backend/app/competitor_site_structure.py`
- `A` — `backend/app/config.py`
- `A` — `backend/app/content_metrics.py`
- `M` — `backend/app/cross_reglue.py`
- `A` — `backend/app/cross_reglue_batch.py`
- `A` — `backend/app/data/mass_main_baseline.json`
- `A` — `backend/app/data/task_search_countries.json`
- `A` — `backend/app/data/template_knowledge/index.json`
- `A` — `backend/app/data/template_knowledge/lemon-casino-pl-lemonbonus24-7.html`
- `M` — `backend/app/db.py`
- `M` — `backend/app/domain_classification.py`
- `A` — `backend/app/domain_redirects.py`
- `A` — `backend/app/domain_redistribution.py`
- `M` — `backend/app/domain_transfer_policy.py`
- `A` — `backend/app/domain_transfer_queue.py`
- `M` — `backend/app/editorial_skill.py`
- `A` — `backend/app/editorial_transport.py`
- `M` — `backend/app/fake_main.py`
- `A` — `backend/app/fake_main_head.py`
- `A` — `backend/app/fake_path_allocation.py`
- `A` — `backend/app/full_content_document.py`
- `A` — `backend/app/full_content_rewrite.py`
- `A` — `backend/app/full_heading_rewrite.py`
- `A` — `backend/app/generation_anchors.py`
- `A` — `backend/app/generation_retry.py`
- `A` — `backend/app/homepage_copy.py`
- `A` — `backend/app/homepage_headings.py`
- `M` — `backend/app/main.py`
- `A` — `backend/app/maintenance_repeat.py`
- `A` — `backend/app/maintenance_reports.py`
- `A` — `backend/app/mass_action_reports.py`
- `A` — `backend/app/mass_action_scope.py`
- `A` — `backend/app/mass_main_targets.py`
- `A` — `backend/app/mass_reglue_launch.py`
- `M` — `backend/app/models.py`
- `A` — `backend/app/move_batch.py`
- `A` — `backend/app/move_plus2.py`
- `A` — `backend/app/naming_variants.py`
- `M` — `backend/app/network_indexing.py`
- `A` — `backend/app/network_reserve.py`
- `A` — `backend/app/network_sitemap.py`
- `M` — `backend/app/network_state.py`
- `A` — `backend/app/network_stock_warning.py`
- `A` — `backend/app/page_backups.py`
- `A` — `backend/app/page_content_expansion.py`
- `M` — `backend/app/page_content_tools.py`
- `A` — `backend/app/page_content_trimming.py`
- `A` — `backend/app/page_editor_drafts.py`
- `A` — `backend/app/page_redirects.py`
- `A` — `backend/app/page_word_count.py`
- `A` — `backend/app/pilot_distribution.py`
- `A` — `backend/app/pilot_internal_pages.py`
- `A` — `backend/app/pilot_internal_pages_policy.py`
- `A` — `backend/app/pilot_mixed.py`
- `A` — `backend/app/pilot_replanning.py`
- `A` — `backend/app/pilot_schemes.py`
- `A` — `backend/app/pilot_scope.py`
- `A` — `backend/app/pilot_streaming.py`
- `A` — `backend/app/pilot_task_search.py`
- `A` — `backend/app/pilot_text_jobs.py`
- `A` — `backend/app/pilot_variations.py`
- `A` — `backend/app/pilot_versions.py`
- `A` — `backend/app/pilot_weekly.py`
- `A` — `backend/app/priority_main_targets.py`
- `M` — `backend/app/project_access.py`
- `M` — `backend/app/project_cache.py`
- `A` — `backend/app/project_interlinking.py`
- `A` — `backend/app/project_inventory_cleanup.py`
- `M` — `backend/app/project_network.py`
- `A` — `backend/app/project_notifications.py`
- `A` — `backend/app/project_notifications_api.py`
- `A` — `backend/app/project_page_autolink.py`
- `M` — `backend/app/project_pages.py`
- `A` — `backend/app/project_structured_data.py`
- `A` — `backend/app/project_table_export.py`
- `A` — `backend/app/prompts/full_page_rewrite.txt`
- `A` — `backend/app/provisioning_readiness.py`
- `A` — `backend/app/reference_context.py`
- `A` — `backend/app/reglue_content.py`
- `A` — `backend/app/reglue_dns.py`
- `A` — `backend/app/reglue_history.py`
- `A` — `backend/app/reglue_journal.py`
- `A` — `backend/app/reglue_monitor.py`
- `A` — `backend/app/reglue_paragraphs.py`
- `A` — `backend/app/reglue_recheck.py`
- `A` — `backend/app/reglue_redirects.py`
- `A` — `backend/app/reglue_reserve_refresh.py`
- `A` — `backend/app/reglue_reserves.py`
- `A` — `backend/app/reglue_reserves_api.py`
- `A` — `backend/app/reglue_title_h1.py`
- `A` — `backend/app/report_ids.py`
- `A` — `backend/app/research_fallback.py`
- `A` — `backend/app/rewrite_policy.py`
- `A` — `backend/app/rewrite_tokens.py`
- `M` — `backend/app/schemas.py`
- `M` — `backend/app/services.py`
- `A` — `backend/app/short_h1.py`
- `A` — `backend/app/showcase_brands.py`
- `M` — `backend/app/site_brands.py`
- `M` — `backend/app/site_templates.py`
- `M` — `backend/app/site_templates_api.py`
- `A` — `backend/app/source_upload.py`
- `A` — `backend/app/structure_home_link.py`
- `A` — `backend/app/structure_research.py`
- `A` — `backend/app/structured_data_generation.py`
- `A` — `backend/app/subdomain_fallback.py`
- `M` — `backend/app/subdomain_naming.py`
- `M` — `backend/app/task_status.py`
- `M` — `backend/app/technical_pages.py`
- `A` — `backend/app/template_bundle.py`
- `M` — `backend/app/template_generated_design.py`
- `A` — `backend/app/template_knowledge.py`
- `A` — `backend/app/template_knowledge_library.py`
- `A` — `backend/app/template_visual_assets.py`
- `A` — `backend/app/title_brand_prefix.py`
- `A` — `backend/app/transfer_confirmation.py`
- `A` — `backend/app/transfer_report_check.py`
- `A` — `backend/app/webdev_read_retry.py`
- `A` — `backend/app/whole_page_brief.py`
- `M` — `backend/app/worker.py`
- `A` — `backend/app/worker_connections.py`
- `A` — `backend/migrations/versions/0062_site_added_to_system.py`
- `A` — `backend/migrations/versions/0063_page_draft_metadata.py`
- `A` — `backend/migrations/versions/0064_template_knowledge.py`
- `A` — `backend/migrations/versions/0065_article_images.py`
- `A` — `backend/migrations/versions/0066_project_notifications.py`
- `A` — `backend/migrations/versions/0067_reglue_reserve_domains.py`
- `A` — `backend/migrations/versions/0068_mass_reglue_participation.py`
- `A` — `backend/migrations/versions/0069_archived_content_urls.py`
- `M` — `backend/requirements.txt`
- `A` — `backend/scripts/classify_jp_net_domains.py`
- `A` — `backend/tests/test_article_images.py`
- `M` — `backend/tests/test_auto_lb.py`
- `A` — `backend/tests/test_auto_lb_keywords.py`
- `A` — `backend/tests/test_auto_pilot.py`
- `M` — `backend/tests/test_auto_reglue.py`
- `A` — `backend/tests/test_base_alternates.py`
- `A` — `backend/tests/test_brand_content_buttons.py`
- `M` — `backend/tests/test_brand_home_links.py`
- `M` — `backend/tests/test_branded_domains.py`
- `A` — `backend/tests/test_competitor_collections.py`
- `M` — `backend/tests/test_cross_reglue.py`
- `A` — `backend/tests/test_cross_reglue_batch.py`
- `A` — `backend/tests/test_domain_redirects.py`
- `A` — `backend/tests/test_domain_redistribution.py`
- `M` — `backend/tests/test_factual_research.py`
- `A` — `backend/tests/test_fake_main_head.py`
- `A` — `backend/tests/test_fake_path_allocation.py`
- `A` — `backend/tests/test_generation_anchors.py`
- `M` — `backend/tests/test_generation_modes.py`
- `A` — `backend/tests/test_homepage_headings.py`
- `A` — `backend/tests/test_main_domain_pins.py`
- `A` — `backend/tests/test_mass_action_scope.py`
- `M` — `backend/tests/test_mass_actions_status.py`
- `A` — `backend/tests/test_mass_content_actions.py`
- `A` — `backend/tests/test_mass_main_targets.py`
- `A` — `backend/tests/test_mass_reglue_launch.py`
- `A` — `backend/tests/test_mass_reglue_reports.py`
- `A` — `backend/tests/test_mass_reserves.py`
- `A` — `backend/tests/test_move_batch.py`
- `A` — `backend/tests/test_move_plus2.py`
- `M` — `backend/tests/test_network_indexing.py`
- `A` — `backend/tests/test_network_lock_pool.py`
- `A` — `backend/tests/test_network_sitemap.py`
- `A` — `backend/tests/test_page_backups.py`
- `A` — `backend/tests/test_page_content_expansion.py`
- `M` — `backend/tests/test_page_content_tools.py`
- `A` — `backend/tests/test_page_draft_migration.py`
- `A` — `backend/tests/test_page_redirects.py`
- `A` — `backend/tests/test_pilot_subdomain_names.py`
- `A` — `backend/tests/test_pilot_variations.py`
- `A` — `backend/tests/test_priority_main_targets.py`
- `M` — `backend/tests/test_project_cache_sync.py`
- `A` — `backend/tests/test_project_identity_flags.py`
- `A` — `backend/tests/test_project_import_exclusions.py`
- `A` — `backend/tests/test_project_interlinking.py`
- `A` — `backend/tests/test_project_inventory_cleanup.py`
- `M` — `backend/tests/test_project_network.py`
- `A` — `backend/tests/test_project_notifications.py`
- `A` — `backend/tests/test_project_page_autolink.py`
- `M` — `backend/tests/test_project_pages.py`
- `A` — `backend/tests/test_project_table_export.py`
- `M` — `backend/tests/test_prompt_rendering.py`
- `A` — `backend/tests/test_redirect_transfer_guards.py`
- `A` — `backend/tests/test_reglue_dns.py`
- `A` — `backend/tests/test_reglue_observations.py`
- `A` — `backend/tests/test_reglue_recheck.py`
- `A` — `backend/tests/test_reglue_reserves.py`
- `A` — `backend/tests/test_reglue_title_h1.py`
- `A` — `backend/tests/test_shortcode_catalog.py`
- `A` — `backend/tests/test_showcase_brands.py`
- `A` — `backend/tests/test_site_added_at.py`
- `M` — `backend/tests/test_site_templates.py`
- `A` — `backend/tests/test_source_upload.py`
- `A` — `backend/tests/test_structure_research.py`
- `A` — `backend/tests/test_subdomain_fallback.py`
- `A` — `backend/tests/test_technical_menu_structure.py`
- `M` — `backend/tests/test_technical_pages.py`
- `A` — `backend/tests/test_template_knowledge.py`
- `A` — `backend/tests/test_template_knowledge_history.py`
- `A` — `backend/tests/test_template_knowledge_library.py`
- `A` — `backend/tests/test_template_knowledge_migration.py`
- `A` — `backend/tests/test_transfer_confirmation.py`
- `A` — `backend/tests/test_transfer_queue_reports.py`
- `M` — `docker-compose.production.yml`
- `M` — `docker-compose.yml`
- `M` — `docs/DEPLOY.md`
- `A` — `docs/TESTING.md`
- `M` — `docs/integrations/webdev-network.md`
- `A` — `frontend/public/brand-icons/betonred-favicon.png`
- `M` — `frontend/public/brand-icons/sources.json`
- `A` — `frontend/src/ArticleImageSettings.tsx`
- `M` — `frontend/src/AutoLbPanel.tsx`
- `A` — `frontend/src/AutoPilot.tsx`
- `M` — `frontend/src/AutoRegluePanel.tsx`
- `A` — `frontend/src/DomainColumnHeader.tsx`
- `A` — `frontend/src/DomainRedirects.tsx`
- `M` — `frontend/src/FactualResearchPanel.tsx`
- `A` — `frontend/src/GenerationAnchors.tsx`
- `A` — `frontend/src/GlobalProjectSearch.tsx`
- `A` — `frontend/src/LastReglueSummary.tsx`
- `A` — `frontend/src/MaintenanceReport.tsx`
- `A` — `frontend/src/MassReglueLaunch.tsx`
- `A` — `frontend/src/MassReglueReports.tsx`
- `A` — `frontend/src/MassScopePicker.tsx`
- `A` — `frontend/src/NetworkIndexingButton.tsx`
- `A` — `frontend/src/NetworkMoveButtons.tsx`
- `M` — `frontend/src/PageContentTools.tsx`
- `A` — `frontend/src/PageRedirects.tsx`
- `A` — `frontend/src/PilotDistribution.tsx`
- `A` — `frontend/src/PilotInternalPages.tsx`
- `A` — `frontend/src/PilotMultiSelect.tsx`
- `A` — `frontend/src/PilotTaskSearch.tsx`
- `A` — `frontend/src/PilotVersionTabs.tsx`
- `A` — `frontend/src/ProjectInterlinking.tsx`
- `M` — `frontend/src/ProjectNetworkPanel.tsx`
- `A` — `frontend/src/ProjectNotifications.tsx`
- `M` — `frontend/src/ProjectPages.tsx`
- `A` — `frontend/src/ProjectStructuredData.tsx`
- `A` — `frontend/src/ReglueJournal.tsx`
- `A` — `frontend/src/ReglueReserves.tsx`
- `A` — `frontend/src/ShortcodeSidebar.tsx`
- `A` — `frontend/src/StructuredDataChanges.tsx`
- `M` — `frontend/src/TemplateCombobox.tsx`
- `M` — `frontend/src/TemplateGenerator.tsx`
- `A` — `frontend/src/TemplateKnowledgeLibrary.tsx`
- `M` — `frontend/src/TemplateSources.tsx`
- `A` — `frontend/src/TransferConfirmation.tsx`
- `A` — `frontend/src/TransferProgress.tsx`
- `A` — `frontend/src/alternateDiff.d.mts`
- `A` — `frontend/src/alternateDiff.mjs`
- `M` — `frontend/src/brandIcons.json`
- `A` — `frontend/src/contentActions.ts`
- `A` — `frontend/src/detailNavigation.ts`
- `A` — `frontend/src/generatedMenuPreview.ts`
- `M` — `frontend/src/main.tsx`
- `A` — `frontend/src/maintenanceRepeat.ts`
- `A` — `frontend/src/massActionScope.ts`
- `A` — `frontend/src/networkReadRetry.ts`
- `A` — `frontend/src/networkReserve.ts`
- `A` — `frontend/src/pageEditorDraft.ts`
- `A` — `frontend/src/pilotDropsNavigation.ts`
- `A` — `frontend/src/pilotReportRoute.ts`
- `A` — `frontend/src/pilotScope.ts`
- `A` — `frontend/src/pilotTextError.ts`
- `A` — `frontend/src/projectNotificationEvents.ts`
- `A` — `frontend/src/siteGeoFilter.ts`
- `M` — `frontend/src/standardAlternates.ts`
- `A` — `frontend/src/styles/auto-pilot.css`
- `A` — `frontend/src/styles/domain-column-header.css`
- `A` — `frontend/src/styles/domain-redirects.css`
- `A` — `frontend/src/styles/global-project-search.css`
- `M` — `frontend/src/styles/global.css`
- `A` — `frontend/src/styles/last-reglue-summary.css`
- `A` — `frontend/src/styles/maintenance-report.css`
- `A` — `frontend/src/styles/pilot-versions.css`
- `M` — `frontend/src/styles/project-pages.css`
- `A` — `frontend/src/styles/project-structured-data.css`
- `A` — `frontend/src/styles/reglue-journal.css`
- `A` — `frontend/src/styles/reglue-reserves.css`
- `M` — `frontend/src/styles/template-generator.css`
- `A` — `frontend/src/styles/transfer-confirmation.css`
- `A` — `frontend/src/templateBrandOptions.ts`
- `A` — `frontend/src/titleRewriteModes.ts`
- `A` — `frontend/src/visiblePoll.ts`
- `A` — `frontend/src/wordDiff.d.mts`
- `A` — `frontend/src/wordDiff.mjs`
- `A` — `frontend/tests/alternateDiff.test.mjs`
- `A` — `frontend/tests/auto_pilot_browser.py`
- `A` — `frontend/tests/competitor_collections_browser.py`
- `A` — `frontend/tests/content_preview_loading_browser.py`
- `A` — `frontend/tests/domain_columns_browser.py`
- `A` — `frontend/tests/domain_redirects_browser.py`
- `A` — `frontend/tests/domain_totals_browser.py`
- `A` — `frontend/tests/fibery_links_browser.py`
- `A` — `frontend/tests/fibery_sync_browser.py`
- `A` — `frontend/tests/footer_menu_browser.py`
- `A` — `frontend/tests/generation_anchors_browser.py`
- `A` — `frontend/tests/interlinking_browser.py`
- `A` — `frontend/tests/mass_actions_browser.py`
- `A` — `frontend/tests/mass_counts_browser.py`
- `A` — `frontend/tests/mass_transfer_browser.py`
- `A` — `frontend/tests/menu_generation_trigger_browser.py`
- `A` — `frontend/tests/networkReserve.test.mjs`
- `A` — `frontend/tests/network_bulk_delete_browser.py`
- `A` — `frontend/tests/network_deletion_status_browser.py`
- `A` — `frontend/tests/network_enter_save_browser.py`
- `A` — `frontend/tests/network_indexing_notice_browser.py`
- `A` — `frontend/tests/network_membership_browser.py`
- `A` — `frontend/tests/network_refresh_browser.py`
- `A` — `frontend/tests/page_expansion_browser.py`
- `A` — `frontend/tests/page_metadata_browser.py`
- `A` — `frontend/tests/page_redirects_browser.py`
- `A` — `frontend/tests/peer_move_browser.py`
- `A` — `frontend/tests/peer_picker_browser.py`
- `A` — `frontend/tests/peer_projects_browser.py`
- `A` — `frontend/tests/project_autolink_browser.py`
- `A` — `frontend/tests/project_pages_dates_browser.py`
- `A` — `frontend/tests/project_table_export_browser.py`
- `A` — `frontend/tests/reglue_reserves_browser.py`
- `A` — `frontend/tests/shortcodes_browser.py`
- `A` — `frontend/tests/siteGeoFilter.test.mjs`
- `A` — `frontend/tests/sites_landing_browser.py`
- `M` — `frontend/tests/standardAlternates.test.mjs`
- `A` — `frontend/tests/technical_menu_browser.py`
- `A` — `frontend/tests/template_knowledge_browser.py`
- `M` — `frontend/tests/template_upload_browser.py`
- `A` — `frontend/tests/title_editor_browser.py`
- `A` — `frontend/tests/transfer-progress.html`
- `A` — `frontend/tests/transferProgressHarness.jsx`
- `A` — `frontend/tests/transfer_queue_browser.py`
- `A` — `frontend/tests/workspace_brand_browser.py`
- `M` — `infra/nginx/production.conf`
- `A` — `infra/nginx/whitelists/whitelist_vpn.conf`
- `A` — `scripts/check_changes.py`
- `A` — `scripts/tests/test_check_changes.py`

## Результат расширенной проверки

Полный backend-набор снимка: **1198 passed, 72 failed** (235,97 с).
Все 72 упавших теста повторно проверены на исходном снимке `2ebaa3d`:
те же 72 ошибки, новых падений от текущей задачи не обнаружено.
Это существующий долг тестов production, а не полностью зелёный набор.
Четыре теста защиты Git-deploy прошли отдельно без браузера.

## Журнал миграций

Alembic показывал 0064, но объекты миграций 0065–0069 уже существовали.
`backend/scripts/reconcile_production_migrations.py` проверяет типы и nullable,
ключи и ограничения, индексы, точные тела функций, триггеры и backfill.
Read-only проверка на production подтвердила соответствие всех объектов.
`--apply` разрешает изменить только alembic_version с 0064 на 0069 после
повторной проверки; таблицы, данные проектов и функции не переписываются.

## Существующие падающие тесты

- `tests/test_api_serialization.py::test_inactive_sites_are_hidden_from_project_lists_and_lookup`
- `tests/test_auto_lb.py::test_prompt_adapts_every_available_language_and_project`
- `tests/test_auto_lb_keywords.py::test_all_supported_languages_and_other_geos_have_localization_contract`
- `tests/test_auto_lb_keywords.py::test_older_general_jobs_are_not_reinterpreted`
- `tests/test_auto_pilot.py::test_update_labels_require_saved_fields_and_include_removed_alternates`
- `tests/test_auto_pilot.py::test_new_preview_cancels_only_own_unfinished_preview_and_retries_are_idempotent`
- `tests/test_auto_pilot.py::test_task_history_only_launches_with_access_pagination_and_no_side_effects`
- `tests/test_auto_reglue.py::test_new_fake_is_current_in_scheme_canonical_and_confirmed_report`
- `tests/test_auto_reglue.py::test_head_without_canonical_confirmation_cannot_complete_or_resend`
- `tests/test_auto_reglue.py::test_subdomain_names_collisions_casino_and_exhaustion`
- `tests/test_auto_reglue.py::test_mixed_naming_is_stable_and_varies_after_each_creation`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[joined-\u041e\u0431\u0449\u0438\u0435 \u043a\u043b\u044e\u0447\u0438]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[joined-]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[joined-None]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[hyphen-\u041e\u0431\u0449\u0438\u0435 \u043a\u043b\u044e\u0447\u0438]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[hyphen-]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[hyphen-None]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[mixed-\u041e\u0431\u0449\u0438\u0435 \u043a\u043b\u044e\u0447\u0438]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[mixed-]`
- `tests/test_auto_reglue.py::test_general_keywords_names_and_exhaustion[mixed-None]`
- `tests/test_auto_reglue.py::test_new_fake_chooses_unused_path_each_iteration_and_current_stays_fixed`
- `tests/test_auto_reglue.py::test_fake_path_templates_exhaustion_and_brand[]`
- `tests/test_auto_reglue.py::test_fake_path_templates_exhaustion_and_brand[\u041e\u0431\u0449\u0438\u0435 \u043a\u043b\u044e\u0447\u0438]`
- `tests/test_auto_reglue.py::test_fake_path_templates_exhaustion_and_brand[Pin-Up]`
- `tests/test_auto_reglue.py::test_fake_path_templates_exhaustion_and_brand[Casino]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[Ice Casino-ice]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[Nine CASINO-nine]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[888 Casino-888]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[King Billy Casino-king]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[CatCasino-cat]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[JoyCasino-joy]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[Casino-X-x]`
- `tests/test_auto_reglue.py::test_fake_path_casino_brands_use_first_word_without_casino[  Verde   Casino  -verde]`
- `tests/test_auto_reglue.py::test_fake_path_skips_normalized_content_and_current_and_validates_metadata`
- `tests/test_auto_reglue.py::test_fake_path_ignores_home_page_but_respects_occupied_internal_pages[/]`
- `tests/test_auto_reglue.py::test_fake_path_ignores_home_page_but_respects_occupied_internal_pages[//]`
- `tests/test_auto_reglue.py::test_fake_path_ignores_home_page_but_respects_occupied_internal_pages[ / ]`
- `tests/test_auto_reglue.py::test_fake_path_ignores_home_page_but_respects_occupied_internal_pages[///]`
- `tests/test_base_alternates.py::test_mass_within_network_replaces_all_links_and_creates_new_current_path[PL-pl]`
- `tests/test_base_alternates.py::test_mass_within_network_replaces_all_links_and_creates_new_current_path[CZ-cs]`
- `tests/test_base_alternates.py::test_mass_within_network_replaces_all_links_and_creates_new_current_path[AZ-az]`
- `tests/test_base_alternates.py::test_mass_within_network_replaces_all_links_and_creates_new_current_path[BR-pt]`
- `tests/test_base_alternates.py::test_cross_missing_language_rejected_before_any_mutation`
- `tests/test_factual_research.py::test_language_retry_does_not_start_fact_check_even_with_competitors_enabled`
- `tests/test_factual_research.py::test_research_opt_out_and_technical_pages_skip_planner[False-False]`
- `tests/test_factual_research.py::test_research_opt_out_and_technical_pages_skip_planner[True-True]`
- `tests/test_fake_path_allocation.py::test_paths_share_a_scope_across_geo_and_brand_spellings_but_not_other_groups`
- `tests/test_fake_path_allocation.py::test_pending_run_and_uncertain_native_assignment_reserve_paths[queued]`
- `tests/test_fake_path_allocation.py::test_pending_run_and_uncertain_native_assignment_reserve_paths[running]`
- `tests/test_fake_path_allocation.py::test_pending_run_and_uncertain_native_assignment_reserve_paths[waiting]`
- `tests/test_fake_path_allocation.py::test_pending_run_and_uncertain_native_assignment_reserve_paths[partial]`
- `tests/test_fake_path_allocation.py::test_batch_allocates_different_paths_before_any_worker_starts`
- `tests/test_fake_path_allocation.py::test_preserved_scheme_replaces_old_fake_path_with_group_unique_path`
- `tests/test_mass_content_actions.py::test_mass_actions_are_idempotent_drafts_and_never_publish[meta_headings]`
- `tests/test_mass_content_actions.py::test_mass_actions_are_idempotent_drafts_and_never_publish[paragraphs]`
- `tests/test_mass_reserves.py::test_selected_reserve_promotes_without_extracting_or_importing[locale_base]`
- `tests/test_page_backups.py::test_rewrite_backs_up_exact_unsaved_source_and_shortcodes_before_gemini`
- `tests/test_pilot_subdomain_names.py::test_no_numbered_names_without_current_numbered_subdomains[Pinco]`
- `tests/test_pilot_subdomain_names.py::test_no_numbered_names_without_current_numbered_subdomains[22Bet]`
- `tests/test_pilot_subdomain_names.py::test_no_numbered_names_without_current_numbered_subdomains[\u041e\u0431\u0449\u0438\u0435 \u043a\u043b\u044e\u0447\u0438]`
- `tests/test_pilot_subdomain_names.py::test_numeric_fallback_requires_existing_numbered_label_and_preserves_history`
- `tests/test_pilot_variations.py::test_reviewed_canonical_and_redirects_reach_webdev`
- `tests/test_pilot_variations.py::test_one_row_refresh_is_idempotent_and_exact_plan_executes`
- `tests/test_project_pages.py::test_ai_jobs_are_durable_and_never_publish`
- `tests/test_redirect_transfer_guards.py::test_redirect_timeout_never_replays_reglue_or_redirect_write_and_no_early_indexing`
- `tests/test_reglue_title_h1.py::test_long_h1_is_fully_shortened_preserving_markup_and_neighbor_content`
- `tests/test_reglue_title_h1.py::test_forced_refresh_uses_fresh_snapshot_and_discards_previous_draft`
- `tests/test_reglue_title_h1.py::test_title_h1_only_backup_and_modified_date_once`
- `tests/test_reglue_title_h1.py::test_preview_only_generates_then_execution_saves_exact_review_once[False]`
- `tests/test_reglue_title_h1.py::test_preview_only_generates_then_execution_saves_exact_review_once[True]`
- `tests/test_structure_research.py::test_topic_precedes_queries_and_serp_and_is_reused`
- `tests/test_transfer_confirmation.py::test_preview_handles_unicode_editorial_urls_and_keeps_ascii_collision_guard`

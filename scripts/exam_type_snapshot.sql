SELECT row_to_json(t) FROM (
 SELECT q.id AS question_id, q.uuid::text AS uuid, d.workspace AS source_system,
 q.source_label, q.display_label, q.prompt_text, q.latex_text,
 q.question_type AS legacy_type, q.question_type_source AS legacy_source,
 q.question_type_human_verified AS legacy_human_verified,
 q.content_mode, q.answer_source, q.source_category, q.record_kind,
 d.title AS document_title, d.filename AS document_filename,
 COALESCE(tp.display_title, tp.title, '') AS topic_title,
 (SELECT json_agg(json_build_object('sha256', a.sha256, 'type', a.asset_type, 'width', a.width, 'height', a.height) ORDER BY a.position, a.id)
  FROM drill_questionasset a WHERE a.question_id=q.id AND a.asset_type IN ('question_crop','answer_crop')) AS assets,
 EXISTS(SELECT 1 FROM drill_questionattempt qa WHERE qa.question_id=q.id AND qa.result IN ('done','correct','review')) AS has_training
 FROM drill_question q
 JOIN drill_questiondocument d ON d.id=q.document_id
 LEFT JOIN drill_questiontopic tp ON tp.id=q.similarity_topic_id
 WHERE q.is_practiceable AND q.record_kind='question' AND d.workspace IN ('ei','drill')
 ORDER BY d.workspace,q.id
) t;

"""Development fallback. PostgreSQL uses DB triggers, including bulk writes."""
from django.db import connection
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from drill.models import (Question, QuestionDocument, QuestionTopic, QuestionExamType,
                          QuestionAsset, QuestionErratum, QuestionSearchDocument)
from drill_sources.models import SourceQuestionAnchor
from .index import enqueue, bump_generations, sync_lexemes

SOURCES = (Question, QuestionDocument, QuestionTopic, QuestionExamType, QuestionAsset, QuestionErratum, SourceQuestionAnchor)

def affected(instance):
    if isinstance(instance, Question):
        return [instance.pk]
    if isinstance(instance, QuestionDocument):
        return list(instance.questions.values_list('pk',flat=True))
    if isinstance(instance, QuestionTopic):
        return list(Question.objects.filter(document_id=instance.document_id).values_list('pk',flat=True))
    return [instance.question_id]

@receiver(pre_save)
def remember_old_search_scope(sender, instance, **kwargs):
    if connection.vendor == 'postgresql' or sender not in SOURCES or not instance.pk:
        return
    old = sender.objects.filter(pk=instance.pk).first()
    if old:
        instance._search_old_ids = affected(old)
        instance._search_old_spaces = list(Question.objects.filter(pk__in=instance._search_old_ids).values_list('document__workspace',flat=True))

@receiver(post_save)
def queue_search_source(sender, instance, raw=False, **kwargs):
    if raw or connection.vendor == 'postgresql' or sender not in SOURCES:
        return
    ids = list(set(affected(instance)+getattr(instance,'_search_old_ids',[])))
    if isinstance(instance,(QuestionAsset,QuestionErratum)):
        bump_generations(Question.objects.filter(pk__in=ids).values_list('document__workspace',flat=True))
    else:
        enqueue(ids)
    bump_generations(getattr(instance,'_search_old_spaces',[]))

@receiver(pre_delete)
def delete_search_source(sender, instance, **kwargs):
    if connection.vendor == 'postgresql':
        return
    if sender is QuestionSearchDocument:
        sync_lexemes(instance.lexeme_refs,[],{})
        bump_generations([instance.workspace])
    elif sender in SOURCES:
        ids = affected(instance)
        bump_generations(Question.objects.filter(pk__in=ids).values_list('document__workspace',flat=True))
        if sender not in (Question,QuestionDocument):
            enqueue(ids)

from django.urls import path

from .views import (
    DrillAssetView,
    DrillCatalogView,
    DrillHeatmapView,
    DrillPaperGenerateView,
    DrillProgressView,
    DrillQuestionAttemptView,
    DrillQuestionDetailView,
    DrillQuestionListView,
    DrillSimilarQuestionView,
)


urlpatterns = [
    path('catalog/', DrillCatalogView.as_view(), name='drill_catalog'),
    path('progress/', DrillProgressView.as_view(), name='drill_progress'),
    path('heatmap/', DrillHeatmapView.as_view(), name='drill_heatmap'),
    path('questions/', DrillQuestionListView.as_view(), name='drill_question_list'),
    path('papers/generate/', DrillPaperGenerateView.as_view(), name='drill_paper_generate'),
    path(
        'questions/<uuid:question_uuid>/',
        DrillQuestionDetailView.as_view(),
        name='drill_question_detail',
    ),
    path(
        'questions/<uuid:question_uuid>/similar/',
        DrillSimilarQuestionView.as_view(),
        name='drill_question_similar',
    ),
    path(
        'questions/<uuid:question_uuid>/attempts/',
        DrillQuestionAttemptView.as_view(),
        name='drill_question_attempt',
    ),
    path('assets/<int:asset_id>/', DrillAssetView.as_view(), name='drill_asset'),
]

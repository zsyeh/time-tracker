from django.urls import path

from .views import (
    DrillAssetView,
    DrillCatalogView,
    DrillHeatmapView,
    DrillBookFeelView,
    DrillCollectionView,
    DrillInsightView,
    DrillPaperGenerateView,
    DrillProgressView,
    DrillQuestionAttemptView,
    DrillQuestionDetailView,
    DrillQuestionListView,
    DrillQuestionMarkerView,
    DrillQuestionUserStateView,
    DrillSimilarQuestionView,
)


urlpatterns = [
    path('catalog/', DrillCatalogView.as_view(), name='drill_catalog'),
    path('progress/', DrillProgressView.as_view(), name='drill_progress'),
    path('heatmap/', DrillHeatmapView.as_view(), name='drill_heatmap'),
    path('collections/', DrillCollectionView.as_view(), name='drill_collections'),
    path('feel/', DrillBookFeelView.as_view(), name='drill_book_feel'),
    path('insight/', DrillInsightView.as_view(), name='drill_insight'),
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
    path(
        'questions/<uuid:question_uuid>/state/',
        DrillQuestionUserStateView.as_view(),
        name='drill_question_user_state',
    ),
    path(
        'questions/<uuid:question_uuid>/markers/',
        DrillQuestionMarkerView.as_view(),
        name='drill_question_markers',
    ),
    path('assets/<int:asset_id>/', DrillAssetView.as_view(), name='drill_asset'),
]

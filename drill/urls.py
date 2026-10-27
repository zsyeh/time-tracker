from django.urls import path
from .circuit_selected_views import CircuitSelectedView
from .signal_selected_views import SignalSelectedView
from .analog_selected_views import AnalogSelectedView
from .digital_selected_views import DigitalSelectedView
from .communication_selected_views import CommunicationSelectedView

from .views import (
    DrillAssetView,
    DrillActivityHeatmapView,
    DrillCatalogView,
    DrillHeatmapView,
    DrillBookFeelView,
    DrillBlueprintListView,
    DrillCollectionView,
    DrillErratumView,
    EiCockpitTopicView,
    EiCockpitView,
    DrillInsightView,
    DrillPaperGenerateView,
    DrillPaperDetailView,
    DrillPaperItemView,
    DrillPaperListCreateView,
    DrillPaperPdfView,
    DrillPaperReviewView,
    DrillPaperShareView,
    DrillProgressView,
    DrillQuestionAttemptView,
    DrillQuestionDetailView,
    DrillQuestionListView,
    DrillQuestionShareView,
    DrillQuestionMarkerView,
    DrillQuestionTimingView,
    DrillQuestionUserStateView,
    DrillSimilarQuestionView,
)


urlpatterns = [
    path('communication-selected/', CommunicationSelectedView.as_view(), name='ei_communication_selected'),
    path('digital-selected/', DigitalSelectedView.as_view(), name='ei_digital_selected'),
    path('analog-selected/', AnalogSelectedView.as_view(), name='ei_analog_selected'),
    path('signal-selected/', SignalSelectedView.as_view(), name='ei_signal_selected'),
    path('circuit-selected/', CircuitSelectedView.as_view(), name='ei_circuit_selected'),
    path('catalog/', DrillCatalogView.as_view(), name='drill_catalog'),
    path('progress/', DrillProgressView.as_view(), name='drill_progress'),
    path('heatmap/', DrillHeatmapView.as_view(), name='drill_heatmap'),
    path('heatmap/activity/', DrillActivityHeatmapView.as_view(), name='drill_activity_heatmap'),
    path('collections/', DrillCollectionView.as_view(), name='drill_collections'),
    path('errata/', DrillErratumView.as_view(), name='drill_errata'),
    path('cockpit/', EiCockpitView.as_view(), name='ei_cockpit'),
    path('cockpit/topics/<int:topic_id>/', EiCockpitTopicView.as_view(), name='ei_cockpit_topic'),
    path('feel/', DrillBookFeelView.as_view(), name='drill_book_feel'),
    path('insight/', DrillInsightView.as_view(), name='drill_insight'),
    path('questions/', DrillQuestionListView.as_view(), name='drill_question_list'),
    path('papers/generate/', DrillPaperGenerateView.as_view(), name='drill_paper_generate'),
    path('papers/blueprints/', DrillBlueprintListView.as_view(), name='drill_blueprints'),
    path('papers/', DrillPaperListCreateView.as_view(), name='drill_papers'),
    path('papers/<uuid:paper_uuid>/', DrillPaperDetailView.as_view(), name='drill_paper_detail'),
    path('papers/<uuid:paper_uuid>/review/', DrillPaperReviewView.as_view(), name='drill_paper_review'),
    path('papers/<uuid:paper_uuid>/share/', DrillPaperShareView.as_view(), name='drill_paper_share'),
    path(
        'papers/<uuid:paper_uuid>/pdf/<str:kind>/',
        DrillPaperPdfView.as_view(),
        name='drill_paper_pdf',
    ),
    path(
        'papers/<uuid:paper_uuid>/items/<int:position>/',
        DrillPaperItemView.as_view(),
        name='drill_paper_item',
    ),
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
        'questions/<uuid:question_uuid>/share/',
        DrillQuestionShareView.as_view(),
        name='drill_question_share',
    ),
    path(
        'questions/<uuid:question_uuid>/timing/',
        DrillQuestionTimingView.as_view(),
        name='drill_question_timing',
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

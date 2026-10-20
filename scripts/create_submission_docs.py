from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
ROOT=Path(__file__).resolve().parents[1]; DOCS=ROOT/'docs'; DOCS.mkdir(exist_ok=True)
NAVY=colors.HexColor('#16324F'); TEAL=colors.HexColor('#2A9D8F'); PALE=colors.HexColor('#EAF2F8')
# Architecture diagram PDF
styles=getSampleStyleSheet(); styles.add(ParagraphStyle(name='DiagramTitle',parent=styles['Title'],alignment=TA_CENTER,textColor=NAVY,fontSize=22,spaceAfter=18))
styles.add(ParagraphStyle(name='Node',parent=styles['BodyText'],alignment=TA_CENTER,fontSize=9,leading=12,textColor=NAVY))
story=[Paragraph('GlucoTwin Architecture',styles['DiagramTitle']),Paragraph('Research proof of concept · synthetic demonstration data only',styles['BodyText']),Spacer(1,18)]
rows=[[Paragraph('<b>Historical profile</b><br/>Synthetic EHR-like context',styles['Node']),Paragraph('<b>Dynamic stream</b><br/>Synthetic timestamped glucose',styles['Node'])],
      [Paragraph('<b>Ingestion & validation</b><br/>Timestamp/value checks · provenance',styles['Node']),Paragraph('<b>Data quality gate</b><br/>Stale · gaps · insufficient data',styles['Node'])],
      [Paragraph('<b>Virtual patient state</b><br/>History · recent observations · audit',styles['Node']),Paragraph('<b>Forecasting</b><br/>Lag features · HistGradientBoosting',styles['Node'])],
      [Paragraph('<b>Explanation & uncertainty</b><br/>Input summaries · heuristic interval',styles['Node']),Paragraph('<b>Persistence & audit</b><br/>JSONL events · forecast history',styles['Node'])],
      [Paragraph('<b>Clinician-facing dashboard</b><br/>Observed vs forecast · quality · scenario lab',styles['Node']),Paragraph('<b>Evaluation pipeline</b><br/>Patient-separated synthetic holdout',styles['Node'])]]
t=Table(rows,colWidths=[245,245],rowHeights=[65,65,65,65,70],hAlign='CENTER')
t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),PALE),('BOX',(0,0),(-1,-1),1,NAVY),('INNERGRID',(0,0),(-1,-1),1,colors.white),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10)]))
story += [t,Spacer(1,14),Paragraph('Flow: both data streams are validated before state update. Accepted observations update the virtual state and clear the previous forecast. A forecast is generated only when sufficient recent observations are available. The dashboard distinguishes observations from predictions and shows quality warnings.',styles['BodyText']),Spacer(1,8),Paragraph('<b>Boundary:</b> historical context is shown in state/dashboard but is not a model feature in this version. No real patient data, device connection, or clinical validation is included.',styles['BodyText'])]
SimpleDocTemplate(str(DOCS/'architecture.pdf'),pagesize=landscape(A4),rightMargin=35,leftMargin=35,topMargin=30,bottomMargin=30).build(story)
# PowerPoint architecture diagram
prs=Presentation(); slide=prs.slides.add_slide(prs.slide_layouts[6])
def textbox(slide,x,y,w,h,text,size=14,bold=False,fill=None):
    shape=slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.text=text
    shape.fill.solid(); shape.fill.fore_color.rgb=__import__('pptx').dml.color.RGBColor(234,242,248) if fill is None else fill
    shape.line.color.rgb=__import__('pptx').dml.color.RGBColor(22,50,79)
    for p in shape.text_frame.paragraphs:
        p.alignment=PP_ALIGN.CENTER
        for r in p.runs:r.font.size=Pt(size);r.font.bold=bold;r.font.color.rgb=__import__('pptx').dml.color.RGBColor(22,50,79)
    return shape
textbox(slide,2.7,.2,5.0,.6,'GlucoTwin Architecture',22,True)
labels=[(0.4,1.2,2.7,.8,'Historical context\nSynthetic profile'),(4.0,1.2,2.7,.8,'Dynamic stream\nSynthetic glucose'),(7.6,1.2,2.7,.8,'Ingestion & validation\nProvenance / value checks'),(2.2,2.6,3.2,.9,'Virtual patient state\nHistory · recent readings · audit'),(6.0,2.6,3.2,.9,'Quality gate\nStale · gaps · insufficient data'),(2.2,4.1,3.2,.9,'Forecasting model\nLag features · HGBR'),(6.0,4.1,3.2,.9,'Explanation / uncertainty\nInput summaries · heuristic band'),(2.2,5.5,7.0,.8,'Dashboard · observed vs predicted · what-if · audit history',15,True)]
for item in labels:
    x,y,w,h,txt,*opts=item; textbox(slide,x,y,w,h,txt,*(opts or [13]))
slide.shapes.add_textbox(Inches(.5), Inches(6.5), Inches(9.8), Inches(.45)).text='Synthetic research prototype only · No clinical validation · Static context included as model features'
prs.save(DOCS/'architecture.pptx')
# Presentation 12 slides
prs=Presentation(); layout=prs.slide_layouts[6]
slides=[
('GlucoTwin','An Explainable, Personalized Glucose Digital Twin\nDigital Twin Challenge 2026 · Team/institution: [fill in]'),
('Problem & intended use','Glucose trajectories change between visits. A single measurement cannot show short-term behavior.\nGoal: fuse historical context with a dynamic glucose stream and forecast near-term values for research review.'),
('Research landscape','Healthcare digital twins are an emerging field. Reviews highlight interoperability, data quality, privacy, ethics and clinical validation.\nExisting examples include Twin Health (commercial personalized metabolic health) and academic digital-twin research.'),
('Opportunity & contribution','Integration-focused PoC: auditable virtual state, input-quality gates, forecast history, explanations, uncertainty signaling and reproducible benchmark.\nNot a claim that glucose forecasting or digital twins are novel.'),
('Prediction task','Input: previous 12 five-minute glucose readings (60 minutes).\nBenchmark target: glucose 30 minutes after input window.\nDashboard forecast: recursive next-step trajectory up to 120 minutes.\nNo diagnosis or treatment recommendation.'),
('Data and provenance','Included: one fictional profile and 288 synthetic glucose readings.\nExternal candidates: DiaTrend (access/terms must be verified); Synthea for synthetic EHR structure.\nNo real CGM data downloaded or evaluated.'),
('Architecture and fusion','Historical profile + dynamic glucose stream → ingestion/validation → virtual state → quality gate + forecast → explanation/audit → dashboard.\nHistorical context is visible in state/UI but not used as model feature in this version.'),
('Dynamic twin workflow','Load SYNTH-001 → inspect source labels → forecast → ingest later reading → state updates and prior forecast clears → generate new forecast.\nInvalid/duplicate/out-of-order readings are rejected and audited.'),
('Evaluation (synthetic only)','Patient-separated split: 18 train IDs / 6 held-out IDs; 10,494 train windows / 3,498 test windows.\nPersistence: MAE 9.468, RMSE 12.304, R² 0.434.\nHistGradientBoosting: MAE 7.003, RMSE 8.975, R² 0.6988.\nSynthetic data only; not clinical evidence.'),
('Reliability, tests, and limitations','Quality checks: malformed/duplicate/out-of-order inputs, stale stream, low observation count, gaps.\n8 automated tests passed in the local environment.\nUncertainty band is heuristic, not calibrated; explanation is descriptive, not causal/SHAP.'),
('Responsible use & next steps','Research/education only; no medical device claims. Do not use for insulin/medication decisions.\nNext: authorized real CGM data, verify dataset licensing, calibration on validation data, external evaluation, clinician review, robustness analysis.'),
('Demo & repository','Run: pip install -r requirements.txt; streamlit run app/dashboard.py; pytest -q; python scripts/evaluate.py.\nRepository/video/team fields must be completed by team. Demo video plan: README.md (20:30+).')]
for title,body in slides:
    s=prs.slides.add_slide(layout)
    titlebox=s.shapes.add_textbox(Inches(.55),Inches(.35),Inches(12.1),Inches(.75)); titlebox.text=title
    for p in titlebox.text_frame.paragraphs:
        for r in p.runs:r.font.size=Pt(27);r.font.bold=True;r.font.color.rgb=__import__('pptx').dml.color.RGBColor(22,50,79)
    bodybox=s.shapes.add_textbox(Inches(.8),Inches(1.45),Inches(11.7),Inches(5.3)); bodybox.text=body
    for p in bodybox.text_frame.paragraphs:
        p.space_after=Pt(16)
        for r in p.runs:r.font.size=Pt(20);r.font.color.rgb=__import__('pptx').dml.color.RGBColor(45,55,65)
    foot=s.shapes.add_textbox(Inches(.6),Inches(7.08),Inches(12),Inches(.25)); foot.text='GlucoTwin · Synthetic research prototype · Not clinically validated'
    for p in foot.text_frame.paragraphs:
        for r in p.runs:r.font.size=Pt(9);r.font.italic=True
prs.save(DOCS/'presentation.pptx')
# Export a matching readable PDF presentation via reportlab
pdfstyles=getSampleStyleSheet(); pdfstyles.add(ParagraphStyle(name='SlideTitle',parent=pdfstyles['Title'],fontSize=24,textColor=NAVY,spaceAfter=24)); pdfstyles.add(ParagraphStyle(name='SlideBody',parent=pdfstyles['BodyText'],fontSize=15,leading=22,spaceAfter=12))
flow=[]
for i,(title,body) in enumerate(slides):
    flow.append(Paragraph(title,pdfstyles['SlideTitle']))
    for para in body.split('\n'):
        flow.append(Paragraph(para.replace('&','&amp;'),pdfstyles['SlideBody']))
    flow.append(Spacer(1,10))
    if i<len(slides)-1: flow.append(PageBreak())
SimpleDocTemplate(str(DOCS/'presentation.pdf'),pagesize=landscape(A4),rightMargin=45,leftMargin=45,topMargin=40,bottomMargin=35).build(flow)
print('Created architecture.pdf, architecture.pptx, presentation.pdf, presentation.pptx')

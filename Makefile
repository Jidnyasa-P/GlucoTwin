PY ?= python
.PHONY: setup data train evaluate test app demo all
setup:    ; $(PY) -m pip install -r requirements.txt
data:     ; $(PY) scripts/generate_synthetic_data.py
train:    ; $(PY) scripts/train.py
evaluate: ; $(PY) scripts/evaluate.py
test:     ; $(PY) -m pytest -q
demo:     ; $(PY) scripts/init_demo.py --reset
app:      ; streamlit run app/dashboard.py
all: data train evaluate demo test

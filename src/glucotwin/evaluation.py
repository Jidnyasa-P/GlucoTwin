import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def regression_metrics(y_true,y_pred):
    return {"n":int(len(y_true)),"mae_mg_dl":round(float(mean_absolute_error(y_true,y_pred)),3),"rmse_mg_dl":round(float(np.sqrt(mean_squared_error(y_true,y_pred))),3),"r2":round(float(r2_score(y_true,y_pred)),4) if len(y_true)>1 else None}

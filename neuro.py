import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn import preprocessing
from sklearn.model_selection import train_test_split

df_train = pd.read_csv('nvkz.csv', header=0)
x_train = df_train.loc[:, 2:]
y_train = df_train.loc[:, 'hotel']

df_test = pd.read_csv('kem.csv', header=0)
x_test = df_train.loc[:, 2:]
y_test = df_train.loc[:, 'hotel']



model_gbm = GradientBoostingClassifier(n_estimators=5000,
                                       learning_rate=0.05,
                                       max_depth=3,
                                       subsample=0.5,
                                       validation_fraction=0.1,
                                       n_iter_no_change=20,
                                       max_features='log2',
                                       verbose=1)
model_gbm.fit(x_train, y_train)
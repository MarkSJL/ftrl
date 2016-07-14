#encoding=utf-8
import numpy as np


from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.base import BaseEstimator
from scipy.sparse import issparse
import cPickle
"""
Created on 2015-09-05
@author: qqian 

this is a Logistic Regression Classifier implementing google's FTRL-proximal(follow the regularized leader) training algorithm

"""
def slice_X(X, start=None, stop=None):
    if type(X) == list:
        if hasattr(start, '__len__'):
            return [x[start] for x in X]
        else:
            return [x[start:stop] for x in X]
    else:
        if hasattr(start, '__len__'):
            return X[start]
        else:
            return X[start:stop]

def make_batches(size, batch_size):
    nb_batch = int(np.ceil(size/float(batch_size)))
    return [(i*batch_size, min(size, (i+1)*batch_size)) for i in range(0, nb_batch)]
    
class FtrlClassifier(BaseEstimator):

    def get_fans(self,shape):
        fan_in = shape[0] if len(shape) == 2 else np.prod(shape[1:])
        fan_out = shape[1] if len(shape) == 2 else shape[0]
        return fan_in, fan_out
    def uniform(self,shape, scale=0.05):
        return np.random.uniform(low=-scale, high=scale, size=shape)

    def glorot_uniform(self,shape):
        fan_in, fan_out = self.get_fans(shape)
        s = np.sqrt(6. / (fan_in + fan_out))
        return self.uniform(shape, s)

    def binary_entropy(self,p, y):
        loss =-(np.array(y) * np.log(p) + (1.0 - np.array(y)) * np.log(1.0 - np.array(p)))
        loss_out = np.zeros(len(y))
        return np.mean(loss)

    def get_weights(self):
        return self.w


    def get_z(self):
        return self.z


    def __init__(self,alpha=0.005, beta=1, l1=0.0, l2=0.0,nb_epoch=20,batch_size=128,early_stop_rounds=None,use_glorot=False):
        """ Get probability estimation on x

            INPUT:
                alpha: float, alpha
                beta: float, beta
                l1: float, l1 penalty
                l2: float, l2 penalty
                nb_epoch: int, number of epochs to train
                batch_size: int,mini batch size
                early_stop_rounds:int, early_stop_rounds only applys when validation_set is used
                use_glorot: boolean, use glorot_uniform to initialize weights default is false
        """
        # parameters for training
        self.alpha = alpha
        self.beta = beta
        self.l1 = l1
        self.l2 = l2
        self.nb_epoch = nb_epoch
        self.iterations =0
        self.batch_size = batch_size
 

        # feature related parameters
        # model
        # n: squared sum of past gradients
        # z: weights
        # w: lazy weights
        self.z = None
        self.n = None
        self.w = None
        self.g = 0.
        # initialize other params
        self.loss = 0.
        self.count = 0
        self.early_stop_rounds = early_stop_rounds
        self.use_glorot= use_glorot

    




    def fit(self,X,y,verbose=1,shuffle=False,validation_set=None):
        if self.z == None and self.n == None and self.w ==None:
            self.input_size = X.shape[1]
            
            self.n = np.zeros(self.input_size)
            
            if self.use_glorot:
                self.w = self.glorot_uniform((self.input_size,))
                self.z = self.glorot_uniform((self.input_size,))
            else:
                self.w = np.zeros(self.input_size)
                self.z = np.zeros(self.input_size)
        batch_size = self.batch_size
        preds = []
        sample_size = X.shape[0]
        index_array = np.arange(sample_size)
        early_stop_rounds=self.early_stop_rounds
        best_auc = 0
        count=0
        for epoch in range(self.nb_epoch):
            if shuffle:
                np.random.shuffle(index_array)
            batches = make_batches(sample_size, batch_size)

            for batch_index, (batch_start, batch_end) in enumerate(batches):
                batch_ids = index_array[batch_start:batch_end]
                ins_batch = slice_X(X, batch_ids)
                outs = self.predict(ins_batch)
                if type(outs) != list:
                    outs = [outs]
                target = y[batch_ids]
                self.update(ins_batch, outs, target)

            if early_stop_rounds and validation_set:
                validation_auc = roc_auc_score(validation_set[1],self.predict_proba(validation_set[0]))
                if best_auc<validation_auc:
                    count=0
                    best_auc = validation_auc
                    f = open("best_ftrl.mdl","wb")
                    cPickle.dump(self,f)
                    f.close()
                
                if count ==early_stop_rounds:
                    validation_auc = roc_auc_score( validation_set[1],self.predict_proba(validation_set[0]))
                    count=0
                    if best_auc>validation_auc:
                        break
                else:
                    count+=1


            if verbose>=1:
                self.loss = self.binary_entropy(self.predict(X), y)
                if validation_set:
                    validation_loss = self.binary_entropy(self.predict(validation_set[0]), validation_set[1])
                    validation_auc = roc_auc_score(validation_set[1],self.predict(validation_set[0]))
                    print('eoch %s\tcurrent_loss: %f\tvalid_loss: %f\tvalid_auc: %f'%(epoch,self.loss,validation_loss,validation_auc))
                else:
                    print('eoch %s\tcurrent loss: %f'%(epoch,self.loss))
        if early_stop_rounds and validation_set:
            
            f = open("best_ftrl.mdl","rb")
            self = cPickle.load(f)
            f.close()
           


    def predict(self,X):
        preds = []
        for x in X: 
            p = self._predict(x)
            preds.append(p)
        return preds

    def predict_proba(self,X):
        return self.predict(X)





    def _predict(self, x):
        ''' Get probability estimation on x

            INPUT:
                x: features

            OUTPUT:
                probability of p(y = 1 | x; W)
        '''
        # parameters
        w = self.get_weights()
        # wTx is the inner product of w and x'
        
        if issparse(x):
            wTx = x.dot(w)[0]

        else:
            wTx = np.dot(x,w)
  
        # cache the current w for update stage
        self.w = w
        # bounded sigmoid function, this is the probability estimation
        p = self.bounded_sigmoid(wTx)

        return p


    def sigmoid(self,inX):  
        return 1.0 / (1 + np.exp(-inX))


    def bounded_sigmoid(self,inX):  
        return 1. / (1. + np.exp(-max(min(inX, 35.), -35.)))
    


    def update(self, x, p, y):
        ''' Update model using x, p, y

            INPUT:
                x: inputs
                p: click probability prediction of our model
                y: target

            MODIFIES:
                self.n: increase by squared gradient
                self.z: weights
        '''
        # gradient under logloss
        #if input is sparse
        if issparse(x):
            self.g = (p-y)*x
        else:
            self.g = np.dot((p - y),x)

        sigma = (np.sqrt(self.n + self.g * self.g) - np.sqrt(self.n)) / self.alpha
        self.z += self.g - sigma * self.w
        self.n += self.g * self.g
        self.iterations +=1
        w = (np.sign(self.z) * self.l1 - self.z) / ((self.beta + np.sqrt(self.n)) / self.alpha + self.l2)
        idx_0 = np.abs(self.z) <= self.l1
        w[idx_0]=0
        self.w = w

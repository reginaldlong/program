import collections
from numpy import *
from nnbase import NNBase
import itertools
import random as rand
import sys

def checkListsEqual(list1, list2):
    if len(list1) != len(list2):
        return False
    for l1, l2 in itertools.izip(list1, list2):
        if l1 != l2:
            return False
    return True

def checkParseEqual(parse1, parse2):
    if len(parse1) != len(parse2):
        return False
    for list1, list2 in itertools.izip(parse1, parse2):
        if not checkListsEqual(list1, list2):
            return False
    return True

class RNN(NNBase):
    """
    Implements an RNN language model of the form:
    h(t) = sigmoid(H * h(t-1) + L[x(t)] + b1)
    y(t) = softmax(U * h(t))
    where y(t) predicts the next word in the sequence

    U = |V| * dim(h) as output vectors
    L = |V| * dim(h) as input vectors

    You should initialize each U[i,j] and L[i,j]
    as Gaussian noise with mean 0 and variance 0.1

    Arguments:
        L0 : initial input word vectors
        U0 : initial output word vectors
        alpha : default learning rate
        bptt : number of backprop timesteps
    """

    def random_weight_matrix(self, m, n):
        e = sqrt(6.0) / sqrt(m + n)
        A0 = random.uniform(-e, e, (m,n))
        return A0


    def __init__(self, L0, middledim=30, reg=1e-5,
                 margin=1, backpropwv=False, alpha=0.005, rseed=10, bptt=1):

        self.hdim = L0.shape[1] # word vector dimensions
        self.vdim = L0.shape[0] # vocab size
        param_dims = dict(H = (self.hdim, self.hdim), W = (middledim, 2*self.hdim), b = (middledim))
        # note that only L gets sparse updates
        param_dims_sparse = dict(L = L0.shape)
        NNBase.__init__(self, param_dims, param_dims_sparse)

        #### YOUR CODE HERE ####


        # Initialize word vectors
        self.sparams.L = L0.copy()
        
        self.params.H = self.random_weight_matrix(*self.params.H.shape)
        
        self.params.W = self.random_weight_matrix(*self.params.W.shape)
        self.params.b = zeros(*self.params.b.shape)

        self.reg = reg
        self.bptt = bptt
        self.alpha = alpha
        self.backpropwv = backpropwv
        self.margin = margin
        #### END YOUR CODE ####

    def sigmoid(self, x):
        return 1.0 / (1.0 + exp(-x))

    def sig_grad(self, x):
        return x*(1 - x)

    def tanh(self, x):
        return 2.0 * self.sigmoid(2.0 * x) - 1

    def tanh_grad(self, f):
        return 1.0 - square(f) 

    def calc_hidden_vec(self, xs, hiddenvec, timenum): 
        for i in xrange(timenum):
            hiddenvec[i + 1] = self.sigmoid(dot(self.params.H, hiddenvec[i]) + self.sparams.L[xs[i]])
    
    def calc_backprop(self, xs, hs, delta):
        siggrads = self.sig_grad(hs)
        i = len(xs) - 1
        dh_curr = delta
        for j in xrange(self.bptt):
            if i - j < 0:
                break   
            dsig = siggrads[i - j + 1]*dh_curr
            self.grads.H += outer(dsig, hs[i - j])
            self.sgrads.L[xs[i - j]] = dsig
            dh_curr = dot(self.params.H.T, dsig)

    def sample_neg(self, answers, question):
        if len(answers[0]) > 1:
            answer = answers[1]
            neg_answer_ind = random.randint(0, len(answers[0]) - 1)
            while checkParseEqual(answers[0][neg_answer_ind], answer):
                neg_answer_ind = random.randint(0, len(answers[0]) - 1)
            return answers[0][neg_answer_ind]
        else: 
            # if there's only one correct parse create janky neg....
            return [[random.randint(0, self._param_dims_sparse['L'][0] - 1)], [random.randint(0, self._param_dims_sparse['L'][0] - 1)]]   
    
    def _acc_grads(self, answers, question):
        """
        Question is (input, command) where both are lists of indices into the word dict.
        Answers is ([all parses], oracle parse) where both are list of 
        """
        #rand.seed(1)
        input_q, command_q = question
        all_parses, oracle = answers
        input_a, command_a = oracle

        input_q = input_q[::-1]
        input_a = input_a[::-1]
        command_q = command_q[::-1]
        command_a = command_a[::-1]


        n_inputq = len(input_q)
        n_commandq = len(command_q)
        n_inputa = len(input_a)
        n_commanda = len(command_a)

        # make matrix here of corresponding h(t)
        # hs[-1] = initial hidden state (zeros)
        # change this computation if we don't want to use the divider
        hs_inputq = zeros((n_inputq + 1, self.hdim))
        hs_commandq = zeros((n_commandq + 1, self.hdim))
        hs_inputa = zeros((n_inputa + 1, self.hdim))
        hs_commanda = zeros((n_commanda + 1, self.hdim))
        
        # Forward propagation
        self.calc_hidden_vec(input_q, hs_inputq, n_inputq)
        self.calc_hidden_vec(command_q, hs_commandq, n_commandq)
        self.calc_hidden_vec(input_a, hs_inputa, n_inputa)
        self.calc_hidden_vec(command_a, hs_commanda, n_commanda)
        
        # Negative sampling
        
        input_neg, command_neg = self.sample_neg(answers, question)
        input_neg = input_neg[::-1]
        command_neg = command_neg[::-1]
        n_inputneg = len(input_neg)
        n_commandneg = len(command_neg)
        
        hs_inputneg = zeros((n_inputneg + 1, self.hdim))
        hs_commandneg = zeros((n_commandneg + 1, self.hdim))

        self.calc_hidden_vec(input_neg, hs_inputneg, n_inputneg)
        self.calc_hidden_vec(command_neg, hs_commandneg, n_commandneg)
        neg_combine = concatenate((hs_inputneg[n_inputneg], hs_commandneg[n_commandneg]))
        hvec_neg = self.tanh(dot(self.params.W, neg_combine) + self.params.b)    
        
        # Forward for question, answer vectors

        q_combine = concatenate((hs_inputq[n_inputq], hs_commandq[n_commandq]))
        a_combine = concatenate((hs_inputa[n_inputa], hs_commanda[n_commanda]))
        
    
        hvec_q = self.tanh(dot(self.params.W, q_combine) + self.params.b)
        hvec_a = self.tanh(dot(self.params.W, a_combine) + self.params.b)        
    
        # For negative sampling, backprop steps
        diff = hvec_q - hvec_a
        diffneg = hvec_q - hvec_neg
        margin = max(0, self.margin - sum(diffneg**2) + sum(diff**2))
        if not margin > 0: return
        
        delta_qneg = -self.tanh_grad(hvec_q)*diffneg
        delta_neg = self.tanh_grad(hvec_neg)*diffneg
        self.grads.W += outer(delta_qneg, q_combine) + outer(delta_neg, neg_combine)
        self.grads.b += delta_qneg + delta_neg

        delta_q = self.tanh_grad(hvec_q)*diff
        delta_a = self.tanh_grad(hvec_a)*(-diff)
        self.grads.W += outer(delta_q, q_combine) + outer(delta_a, a_combine)
        self.grads.b += delta_q + delta_a

        self.grads.W += self.reg*self.params.W
        

        if not self.backpropwv: return

        d_qcombine = dot(self.params.W.T, delta_q + delta_qneg)
        d_acombine = dot(self.params.W.T, delta_a)
        d_negcombine = dot(self.params.W.T, delta_neg)    
    
        delta_inputq = d_qcombine[0:self.hdim]
        delta_commandq = d_qcombine[self.hdim:]
        delta_inputa = d_acombine[0:self.hdim]
        delta_commanda = d_acombine[self.hdim:]
        delta_inputneg = d_negcombine[0:self.hdim]
        delta_commandneg = d_negcombine[self.hdim:]        

        self.calc_backprop(input_q, hs_inputq, delta_inputq)
        self.calc_backprop(input_a, hs_inputa, delta_inputa)
        self.calc_backprop(command_q, hs_commandq, delta_commandq)
        self.calc_backprop(command_a, hs_commanda, delta_commanda)
        self.calc_backprop(command_neg, hs_commandneg, delta_commandneg)
        self.calc_backprop(input_neg, hs_inputneg, delta_inputneg)
    
    def grad_check(self, x, y, outfd=sys.stderr, **kwargs):
        """
        Wrapper for gradient check on RNNs;
        ensures that backprop-through-time is run to completion,
        computing the full gradient for the loss as summed over
        the input sequence and predictions.

        Do not modify this function!
        """
        bptt_old = self.bptt
        self.bptt = 100
        print >> outfd, "NOTE: temporarily setting self.bptt = len(y) = %d to compute true gradient." % self.bptt
        NNBase.grad_check(self, x, y, outfd=outfd, **kwargs)
        self.bptt = bptt_old
        print >> outfd, "Reset self.bptt = %d" % self.bptt


    def predict_single(self, answers, question):
        input_q, command_q = question
        all_parses, oracle = answers
        input_q = input_q[::-1]
        command_q = command_q[::-1]
        n_inputq = len(input_q)
        n_commandq = len(command_q)
        hs_inputq = zeros((n_inputq + 1, self.hdim))
        hs_commandq = zeros((n_commandq + 1, self.hdim))
        
        self.calc_hidden_vec(input_q, hs_inputq, n_inputq) 
        self.calc_hidden_vec(command_q, hs_commandq, n_commandq)
        
        qcombine = concatenate((hs_inputq[n_inputq], hs_commandq[n_commandq]))
        hvec_q = self.tanh(dot(self.params.W, qcombine) + self.params.b)

        minCost = inf
        minCostIndex = -1   
        
        for i, candidate in enumerate(all_parses):
            input_a, command_a = candidate
            input_a = input_a[::-1]
            command_a = command_a[::-1]
            n_inputa = len(input_a)
            n_commanda = len(command_a)
            hs_inputa = zeros((n_inputa + 1, self.hdim))
            hs_commanda = zeros((n_commanda + 1, self.hdim))
            self.calc_hidden_vec(input_a, hs_inputa, n_inputa)
            self.calc_hidden_vec(command_a, hs_commanda, n_commanda)
            
            acombine = concatenate((hs_inputa[n_inputa], hs_commanda[n_commanda]))
            hvec_a = self.tanh(dot(self.params.W, acombine) + self.params.b)

            cost = sum((hvec_q - hvec_a)**2)
            if cost < minCost:
                minCostIndex = i
                minCost = cost
        return minCostIndex

    def predict(self, parses, utterances):
        outputs = []
        for parseSet, utterance in itertools.izip(parses, utterances):
            outputs.append(self.predict_single(parseSet, utterance))
        return outputs
        
    def compute_single_loss(self, answers, question):
        """
        Compute the total cross-entropy loss
        for an input sequence xs and output
        sequence (labels) ys.

        You should run the RNN forward,
        compute cross-entropy loss at each timestep,
        and return the sum of the point losses.
        """
        #rand.seed(1)
        input_q, command_q = question
        all_parses, oracle = answers
        input_a, command_a = oracle
        input_q = input_q[::-1]
        input_a = input_a[::-1]
        command_q = command_q[::-1]
        command_a = command_a[::-1]


        n_inputq = len(input_q)
        n_commandq = len(command_q)
        n_inputa = len(input_a)
        n_commanda = len(command_a)

        # make matrix here of corresponding h(t)
        # hs[-1] = initial hidden state (zeros)
        # change this computation if we don't want to use the divider
        hs_inputq = zeros((n_inputq + 1, self.hdim))
        hs_commandq = zeros((n_commandq + 1, self.hdim))
        hs_inputa = zeros((n_inputa + 1, self.hdim))
        hs_commanda = zeros((n_commanda + 1, self.hdim))
        
        # Forward propagation
        self.calc_hidden_vec(input_q, hs_inputq, n_inputq)
        self.calc_hidden_vec(command_q, hs_commandq, n_commandq)
        self.calc_hidden_vec(input_a, hs_inputa, n_inputa)
        self.calc_hidden_vec(command_a, hs_commanda, n_commanda)
 
        # Negative sampling
        
        input_neg, command_neg = self.sample_neg(answers, question)
        input_neg = input_neg[::-1]
        command_neg = command_neg[::-1]
        n_inputneg = len(input_neg)
        n_commandneg = len(command_neg)
        hs_inputneg = zeros((n_inputneg + 1, self.hdim))
        hs_commandneg = zeros((n_commandneg + 1, self.hdim))

        self.calc_hidden_vec(input_neg, hs_inputneg, n_inputneg)
        self.calc_hidden_vec(command_neg, hs_commandneg, n_commandneg)
        neg_combine = concatenate((hs_inputneg[n_inputneg], hs_commandneg[n_commandneg]))
        hvec_neg = self.tanh(dot(self.params.W, neg_combine) + self.params.b)    
       
        # Forward for question, answer vectors

        q_combine = concatenate((hs_inputq[n_inputq], hs_commandq[n_commandq]))
        a_combine = concatenate((hs_inputa[n_inputa], hs_commanda[n_commanda]))
        
    
        hvec_q = self.tanh(dot(self.params.W, q_combine) + self.params.b)
        hvec_a = self.tanh(dot(self.params.W, a_combine) + self.params.b)        
    
        # For negative sampling, backprop steps
        diff = hvec_q - hvec_a
        diffneg = hvec_q - hvec_neg
        margin = max(0, self.margin - 0.5*sum(diffneg**2) + 0.5*sum(diff**2))
        J = margin + 0.5*self.reg*sum(self.params.W**2)
        return J

    def compute_loss(self, X, Y):
        """
        Compute total loss over a dataset.
        (wrapper for compute_seq_loss)

        Do not modify this function!
        """
        if not isinstance(Y[0][0], collections.Iterable): # single example
            return self.compute_single_loss(X, Y)
        else: # multiple examples
            return sum([self.compute_single_loss(answers, question)
                       for answers, question in itertools.izip(X, Y)])

    def compute_mean_loss(self, X, Y):
        """
        Normalize loss by total number of points.

        Do not modify this function!
        """
        J = self.compute_loss(X, Y)
        ntot = sum(map(len,Y))
        return J / float(ntot)

if __name__ == "__main__":
    rnn = RNN(sqrt(0.1)*random.standard_normal((1000, 5)), backpropwv = True)
    utterExample = [[411, 339, 46], [341, 591, 83, 355, 175]]
    trainExample = ([([411, 339, 46], [341, 591, 83, 355, 175])], ([21, 1], [2, 3, 4]))
    rnn.grad_check(trainExample, utterExample)
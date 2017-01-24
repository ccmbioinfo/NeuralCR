import tensorflow as tf
import numpy as np


def weight_variable(name, shape):
    return tf.get_variable(name, shape = shape, initializer = tf.random_normal_initializer(stddev=0.1))
    return tf.get_variable(name, shape, initializer=tf.contrib.layers.xavier_initializer())

def linear(name, x, shape):
#    w = tf.get_variable(name+"W", shape, initializer=tf.contrib.layers.xavier_initializer())
    w = tf.get_variable(name+"W", shape = shape, initializer = tf.random_normal_initializer(stddev=0.1))
#    w = weight_variable(name+"W", shape)
    b = tf.get_variable(name+"B", shape = shape[1], initializer = tf.random_normal_initializer(stddev=0.1))
#    b = weight_variable(name+"B", [shape[1]])
    return tf.matmul(x,w) + b

def embedding_variable(name, shape):
    return tf.get_variable(name, shape = shape, initializer = tf.random_normal_initializer(stddev=0.1))

class NCRModel():
    def get_HPO_embedding(self, indices=None):
        embedding = self.HPO_embedding
        if indices is not None:
            embedding = tf.gather(self.HPO_embedding, indices)
            return embedding #tf.maximum(0.0, embedding)

    def apply_rnn(self, seq, seq_length):
            #seq_embeded = tf.nn.embedding_lookup(self.word_embedding, seq)
#		inputs = [tf.squeeze(input_, [1]) for input_ in tf.split(1, self.config.max_sequence_length, seq_embeded)]
            inputs = [tf.squeeze(input_, [1]) for input_ in tf.split(1, self.config.max_sequence_length, seq)]
            '''
            w1 = weight_variable('layer1W', [self.config.word_embed_size, self.config.l1_size])
            b1 = weight_variable('layer1B', [self.config.l1_size])
            w2 = weight_variable('layer2W', [self.config.l1_size, self.config.l2_size])
            b2 = weight_variable('layer2B', [self.config.l2_size])
            '''
            '''
            w3 = weight_variable('layer3W', [l3_size, l3_size])
            b3 = weight_variable('layer3B', [l3_size])
            '''
            '''

            mlp_inputs = [tf.nn.tanh(tf.matmul(x, w1)+b1) for x in inputs]
            mlp_inputs = [tf.nn.tanh(tf.matmul(x, w2)+b2) for x in mlp_inputs]
            #mlp_inputs = [tf.nn.tanh(tf.matmul(x, w3)+b3) for x in mlp_inputs]
            '''
            cell = tf.nn.rnn_cell.GRUCell(self.config.hidden_size, activation=tf.nn.tanh)

            _, state = tf.nn.rnn(cell, inputs, dtype=tf.float32, sequence_length=seq_length)
            #_, state = tf.nn.rnn(cell, mlp_inputs, dtype=tf.float32, sequence_length=seq_length)
            return state

    def apply_meanpool(self, seq, seq_length):
        #filters1 = tf.get_variable('conv1', [1, self.config.word_embed_size, self.config.hidden_size], tf.float32, initializer=tf.random_normal_initializer(stddev=0.1))
        filters1 = tf.get_variable('conv1', [1, self.config.word_embed_size, self.config.hidden_size], tf.float32, initializer=tf.contrib.layers.xavier_initializer())
        #conv1_b = tf.get_variable('conv1_b', initializer=tf.random_normal_initializer(stddev=0.1), shape=self.config.hidden_size)
        conv1_b = tf.get_variable('conv1_b', initializer=tf.contrib.layers.xavier_initializer(), shape=self.config.hidden_size)
        layer1 = tf.nn.relu(tf.nn.conv1d(seq, filters1, 1, padding='SAME')+conv1_b)

        #filters2 = tf.get_variable('conv2', [1, self.config.hidden_size, self.config.hidden_size], tf.float32, initializer=tf.random_normal_initializer(stddev=0.1))
        filters2 = tf.get_variable('conv2', [1, self.config.hidden_size, self.config.hidden_size], tf.float32, initializer=tf.contrib.layers.xavier_initializer())
        #conv2_b = tf.get_variable('conv2_b', initializer=tf.random_normal_initializer(stddev=0.1), shape=self.config.hidden_size)
        conv2_b = tf.get_variable('conv2_b', initializer=tf.contrib.layers.xavier_initializer(), shape=self.config.hidden_size)
        layer2 = tf.nn.relu(tf.nn.conv1d(layer1, filters2, 1, padding='SAME')+conv2_b)

        return tf.reduce_max(layer2, [1])
        #return tf.reduce_sum(layer2, [1])

    #############################
    ##### Creates the model #####
    #############################
    def __init__(self, config, training = False, ancs_sparse = None):
        self.config = config

        if ancs_sparse is None:
            self.ancestry_masks = tf.get_variable("ancestry_masks", [config.hpo_size, config.hpo_size], trainable=False)
        else:
            ancestry_sparse_tensor = tf.sparse_reorder(tf.SparseTensor(indices = ancs_sparse, values = [1.0]*len(ancs_sparse), shape=[config.hpo_size, config.hpo_size]))

        ### Inputs ###
        self.input_hpo_id = tf.placeholder(tf.int32, shape=[None])
        self.input_sequence = tf.placeholder(tf.float32, shape=[None, config.max_sequence_length, config.word_embed_size])
        self.input_sequence_lengths = tf.placeholder(tf.int32, shape=[None])
        label = tf.one_hot(self.input_hpo_id, config.hpo_size)

#        self.gru_state = self.apply_rnn(self.input_sequence, self.input_sequence_lengths) 
        self.gru_state = self.apply_meanpool(self.input_sequence, self.input_sequence_lengths) 

        layer1 = tf.nn.relu(linear('sm_layer1', self.gru_state, [self.config.hidden_size, self.config.layer1_size]))
        self.layer2 = tf.nn.relu(linear('sm_layer2', layer1, [self.config.layer1_size, self.config.layer2_size]))
        self.layer3 = tf.nn.relu(linear('sm_layer3', self.layer2, [self.config.layer2_size, self.config.layer3_size]))

        layer1_para = tf.nn.relu(linear('sm_layer1_para', self.gru_state, [self.config.hidden_size, self.config.layer1_size]))
        layer2_para = tf.nn.relu(linear('sm_layer2_para', layer1_para, [self.config.layer1_size, self.config.layer2_size]))
#        layer3 = tf.nn.relu(linear('sm_layer3', layer2, [self.config.layer2_size, self.config.layer3_size]))
       
        init_w = tf.constant((np.random.normal(0.0,0.1,[self.config.layer2_size, self.config.hpo_size])), dtype=tf.float32)
        last_layer_w = tf.get_variable('last_layer_w', initializer=init_w)

        init_w_para = tf.constant(np.abs(np.random.normal(0.0,0.1,[self.config.layer2_size, self.config.hpo_size])), dtype=tf.float32)
        last_layer_w_para = tf.get_variable('last_layer_w_para', initializer=init_w_para)

        init_b = tf.constant((np.random.normal(0.0,0.1,[self.config.hpo_size])), dtype=tf.float32)
        last_layer_b = tf.get_variable('last_layer_b', initializer=init_b)

        self.layer4= (linear('sm_layer4', self.layer2, [self.config.layer2_size, self.config.hpo_size]))
#        self.layer4= tf.matmul(self.layer2, (last_layer_w)) # + last_layer_b
        self.layer4_para= (linear('sm_layer4_para', layer2_para, [self.config.layer2_size, self.config.hpo_size]))
        #self.layer4_para = tf.matmul(layer2_para, tf.nn.relu(last_layer_w_para))# + last_layer_b
        #self.layer4= (linear('sm_layer4', self.layer2, [self.config.layer2_size, self.config.hpo_size]))
        #self.layer4= tf.nn.tanh(linear('sm_layer4', layer3, [self.config.layer3_size, self.config.hpo_size]))


        #mixing_w = tf.Variable(1.0)
        mixing_w= tf.nn.sigmoid(tf.Variable(0.0))
       # self.score_layer = (mixing_w * self.layer4 +\
        '''
        self.score_layer = (mixing_w * self.layer4 + tf.minimum(self.layer4, tf.zeros_like(self.layer4)) +\
                tf.matmul(tf.maximum(self.layer4, tf.zeros_like(self.layer4)), tf.transpose(self.ancestry_masks)))
        '''
        ### TODO!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!  ancestry_sparse_matrix
        if ancs_sparse is None:
            self.score_layer = (mixing_w * self.layer4 + tf.minimum(self.layer4, tf.zeros_like(self.layer4)) +\
                    tf.matmul(tf.maximum(self.layer4, tf.zeros_like(self.layer4)), tf.transpose(self.ancestry_masks)))
#            self.score_layer =  tf.matmul(self.layer4, tf.transpose(self.ancestry_masks))
        else:
#            self.score_layer =  self.layer4
            self.score_layer = mixing_w * self.layer4 + tf.minimum(self.layer4, tf.zeros_like(self.layer4)) +\
                    tf.transpose(tf.sparse_tensor_dense_matmul(ancestry_sparse_tensor, tf.transpose(tf.maximum(self.layer4, tf.zeros_like(self.layer4)))))
#            self.score_layer = self.layer4_para + tf.transpose(tf.sparse_tensor_dense_matmul(ancestry_sparse_tensor, tf.transpose(self.layer4)))
#            self.score_layer = mixing_w*self.layer4 + tf.transpose(tf.sparse_tensor_dense_matmul(ancestry_sparse_tensor, tf.transpose(self.layer4)))

        self.pred = tf.nn.softmax(self.score_layer)
        #self.pred = tf.nn.softmax(self.score_layer + last_layer_b)

        if training:
            l2_w = 0.0
            self.loss = tf.reduce_mean(\
                    tf.nn.softmax_cross_entropy_with_logits(self.score_layer, label)) # + l2_w * tf.reduce_sum(tf.nn.relu(last_layer_w_para))


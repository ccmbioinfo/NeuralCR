import argparse
import phraseConfig
import phrase_model 
import accuracy
import fasttext_reader as reader
import numpy as np
import sys
import sent_level
import sent_accuracy
import time
import os
import h5py
from onto import Ontology
import fasttext
 

def new_train(model):
    report_len = 20
    num_epochs = 40 

    rd = reader.Reader(model.ont)
    samplesFile = open("data/labeled_data")
    samples = accuracy.prepare_phrase_samples(model.ont, samplesFile, True)
    training_samples = {}
    for hpid in model.ont.names:
        for s in model.ont.names[hpid]:
            training_samples[s]=[hpid]

    ubs = [Ontology('data/uberon.obo', root) for root in ["UBERON:0000062", "UBERON:0000064"]]
    negs = set([name for ub in ubs for concept in ub.names for name in ub.names[concept]])
    model.init_training()
    model.init_training(negs)
    
    for epoch in range(num_epochs):
        print "epoch ::", epoch
	rd.reset_counter()
        model.train_epoch()
        for x in model.get_hp_id(['retina cancer'], 10)[0]:
            if x[0] in model.ont.names:
                print model.ont.names[x[0]], x[1]
            else:
                print x[0], x[1]
        #for x in ant.get_hp_id(['skeletal anomalies'], 10)[0]:
        if ((epoch>0 and epoch % 5 == 0)) or epoch == num_epochs-1:
            hit, total = accuracy.find_phrase_accuracy(model, samples, 5, False)
            print "R@5 Accuracy on test set ::", float(hit)/total
            hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
            print "R@1 Accuracy on test set ::", float(hit)/total
        if ((epoch>0 and epoch % 10 == 0)) or epoch == num_epochs-1:
            hit, total = accuracy.find_phrase_accuracy(model, training_samples, 1, False)
            print "Accuracy on training set ::", float(hit)/total
    return model

def grid_search():
    config = phraseConfig.Config
    rd = reader.Reader(open("data/hp.obo"), False)
    config.update_with_reader(rd)

    samplesFile = open("data/labeled_data")
    samples = accuracy.prepare_phrase_samples(rd, samplesFile, True)

    training_samples = {}
    for hpid in rd.names:
        for s in rd.names[hpid]:
            training_samples[s]=[hpid]
    
    for config.batch_size in [256, 128]:
        for config.lr in [0.002, 0.001, 0.004]:
            for config.hidden_size in [512, 1024]:
                for config.layer1_size in [1024]:
                    for config.layer2_size in [1024, 2048]:
                        config.layer3_size = config.layer2_size
                        config.layer4_size = config.layer2_size

                        model = phrase_model.NCRModel(config, rd)
                        num_epochs = 20 
                        for epoch in range(num_epochs):
                            print "epoch ::", epoch
                            model.train_epoch()
                        hit, total = accuracy.find_phrase_accuracy(model, samples, 5, False)
                        r5 = float(hit)/total
                        hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
                        r1 = float(hit)/total
                        hit, total = accuracy.find_phrase_accuracy(model, training_samples, 1, False)
                        tr1 = float(hit)/total

                        with open("grid_results.txt","a") as testResultFile:
                            testResultFile.write('lr: ' + str(config.lr) +\
                                        '\tbatch_size ' + str(config.batch_size) +\
                                        '\thidden_size ' + str(config.hidden_size) +\
                                        '\tlayer1_size ' + str(config.layer1_size) +\
                                        '\tlayer2_size ' + str(config.layer2_size) +\
                                        '\tlayer3_size ' + str(config.layer2_size) +\
                                        '\tr5: '+ str(r5) +\
                                        '\tr1: '+ str(r1) +\
                                        '\ttr1: '+ str(tr1)+ "\n")                            

def interactive_sent(model):
#    model.set_anchors()
    textAnt = sent_level.TextAnnotator(model)
    while True:
        print "Enter querry:"
        text = sys.stdin.readline()
        if text == "":
            break
        start_time = time.time()
        results = textAnt.process_text(text, 0.6, True)
        end_time = time.time()
        for res in results:
            print "["+str(res[0])+"::"+str(res[1])+"]\t" , res[2], "|", text[res[0]:res[1]], "\t", res[3], "\t", model.rd.names[res[2]]
        print "Time elapsed: "+ ("%.2f" % (end_time-start_time)) + "s"

def interactive(model):
    while True:
        sys.stdout.write("-----------\nEnter text:\n")
        sys.stdout.flush()
        text = sys.stdin.readline()
        sys.stdout.write("\n")
        matches = model.get_hp_id([text],15)
        for x in matches[0]:
            '''
            if x[0] == 'None':
                sys.stdout.write(x[0]+' '+str('None')+' '+str(x[1])+'\n')
            else:
            '''
            sys.stdout.write(x[0]+' '+str(model.rd.names[x[0]])+' '+str(x[1])+'\n')
        sys.stdout.write("\n")
	
def anchor_test(model):
    samples = accuracy.prepare_phrase_samples(model.rd, open("data/labeled_data"), True)
    training_samples = {}

    model.set_anchors(syns, syn_labels)
    #model.save_params(repdir)

    for x in model.get_hp_id(['retina cancer'], 10)[0]:
        print model.rd.names[x[0]], x[1]
    print "==="
    for x in model.get_hp_id(['retinal neoplasm'], 10)[0]:
        print model.rd.names[x[0]], x[1]

    hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
    r1 = float(hit)/total
    print "R@1 Accuracy on test set ::", r1

    text_ant = sent_level.TextAnnotator(model)
    sent_window_func = lambda text: [x[2] for x in text_ant.process_text(text, 0.8, True )]
    sent_accuracy.find_sent_accuracy(sent_window_func, "labeled_sentences.p", model.rd)
#    sent_accuracy.compare_methods(sent_accuracy.biolark_wrapper.process_sent, sent_window_func, "labeled_sentences.p", model.rd)

def get_model(repdir, config):
    rd = reader.Reader("data/", True)
    #rd = reader.Reader(open("data/hp.obo"), True)
    model = phrase_model.NCRModel(config, rd)
    model.load_params(repdir)
    return model

def sent_test(model, threshold=0.6):
  #  model.set_anchors()
    #text_ant = sent_level.TextAnnotator(model)
    #sent_window_func = lambda text: [x[2] for x in text_ant.process_text(text, 0.6, True )]
    sent_window_func = lambda text: [x[2] for x in model.annotate_text(text,threshold)]
    sent_accuracy.find_sent_accuracy(sent_window_func, "labeled_sentences.p", model.rd)
    #sent_accuracy.compare_methods(sent_accuracy.biolark_wrapper.process_sent, sent_window_func, "labeled_sentences.p", model.rd)

def phrase_test(model):
    samples = accuracy.prepare_phrase_samples(model.ont, open("data/labeled_data"), True)
    training_samples = {}
    for hpid in model.ont.names:
        for s in model.ont.names[hpid]:
            training_samples[s]=[hpid]

    hit, total = accuracy.find_phrase_accuracy(model, samples, 5, True)
    r5 = float(hit)/total
    print "R@5 Accuracy on test set ::", r5
    hit, total = accuracy.find_phrase_accuracy(model, samples, 1, False)
    r1 = float(hit)/total
    print "R@1 Accuracy on test set ::", r1
    hit, total = accuracy.find_phrase_accuracy(model, training_samples, 1, False)
    tr1 = float(hit)/total
    print "R@1 Accuracy on training set ::", tr1

def udp_test(model, text_file, phe_file, bk_file):
    retrieved = []
    textAnt = sent_level.TextAnnotator(model)
    text = open(text_file).read()
    called = set([x[2] for x in textAnt.process_text(text, 0.6, True)])
    real_phe = set([model.rd.concepts[model.rd.name2conceptid[name.strip().lower()]] for name in open(phe_file).readlines()])

    bk_called = [model.rd.real_id[x.strip()] for x in open(bk_file).readlines()]

    print "NCR:"
    true_pos = [x for x in called if x in real_phe]
    print len(called), len(real_phe), len(true_pos)
    print "Precision:", 1.0*len(true_pos)/len(called)
    print "Recall:", 1.0*len(true_pos)/len(real_phe)

    print "Biolark:"
    bk_true_pos = [x for x in bk_called if x in real_phe]
    print len(bk_called), len(real_phe), len(bk_true_pos)
    print "Precision:", 1.0*len(bk_true_pos)/len(bk_called)
    print "Recall:", 1.0*len(bk_true_pos)/len(real_phe)

def main():
    parser = argparse.ArgumentParser(description='Hello!')
    parser.add_argument('--repdir', help="The location where the checkpoints and the logfiles will be stored, default is \'checkpoints/\'", default="checkpoints/")
    parser.add_argument('--udp_prefix', help="", default="chert")
    args = parser.parse_args()

    config = phraseConfig.Config
#    udp_test(get_model(args.repdir, config), args.udp_prefix+".txt", args.udp_prefix+".phe", args.udp_prefix+".txt.bk")
#    interactive_sent(get_model(args.repdir, config))
#    exit()
    #sent_test(get_model(args.repdir, config))
    ###########
    '''
    model = get_model(args.repdir, config)

    ## print graph
    with  open('graph.txt','w') as graphfile:
        for hpid in model.rd.kids:
            for hpkid in model.rd.kids[hpid]:
                graphfile.write(str(model.rd.concept2id[hpid])+' '+str(model.rd.concept2id[hpkid])+'\n')
    exit()
    ## print graph
    W = model.sess.run(model.w)
    aggW = model.sess.run(model.aggregated_w)
    y = np.zeros(len(model.rd.concepts))
    y_sum = np.zeros(len(model.rd.concepts))
    top_terms = model.rd.kids["HP:0000118"]
    top_term_ids = [model.rd.concept2id[x] for x in top_terms]
    for h_id in range(len(model.rd.concepts)-1):
        for i,top_id in enumerate(top_term_ids):
            if model.rd.ancestry_mask[h_id, top_id] == 1:
                y[h_id] = i+1
        y_sum[h_id] = np.sum(model.rd.ancestry_mask[h_id,:])
 
    from tsne import bh_sne
    taggW = bh_sne(aggW.astype(np.float))
    h5f = h5py.File('embeddings.h5', 'w')
    h5f.create_dataset('W', data=W)
    h5f.create_dataset('aggW', data=aggW)
    h5f.create_dataset('taggW', data=taggW)
    h5f.create_dataset('y', data=y)
    h5f.create_dataset('y_sum', data=y_sum)
    h5f.close()
    exit()
    '''
    ###########


    #phrase_test(get_model(args.repdir, config))
    #anchor_test(get_model(args.repdir, config))

    #interactive(get_model(args.repdir, config)) 
    #exit()

    #grid_search()

    word_model = fasttext.load_model('data/model_pmc.bin')
    ont = Ontology('data/hp.obo',"HP:0000118")
    model = new_train(phrase_model.NCRModel(config, ont, word_model))
    model.save_params(args.repdir)
    '''
    model = phrase_model.NCRModel(config, ont, word_model)
    model.load_params(args.repdir)
    phrase_test(model)
    '''

if __name__ == "__main__":
	main()


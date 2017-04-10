# min-heap library
import heapq as hq

# pre-processing utilities
from myutils import cosine

# Standford POS Tagger
# CLASSPATH env-var contains path to JAR
from nltk.tag import StanfordPOSTagger
from nltk.internals import config_java

POS_TAGS = [ "CC", "CD", "DT", "EX", "FW", "IN", "JJ", "JJR", "JJS", \
    "LS", "MD", "NN", "NNP", "NNPS", "NNS", "PDT", "POS", "PRP", "PRP$", \
    "RB", "RBR", "RBS", "RP", "SYM", "TO", "UH", "VB", "VBD", "VBG", "VBN", \
    "VBP", "VBZ", "WDT", "WP", "WP$", "WRB", "#", "$", "''", "(", ")", ",", ".", ":", "``" ]

def auxAdd(x, y):
    if x is None:
        return y
    x += y
    return x

tagger_cache = {}

""" Get semantic and metadata features """
def getFeatures(model, q_w, c_w, rank, config):
    # model : doc2vec model trained on corpus
    # q_w   : words of question text
    # c_w   : words of comment text
    # rank  : rank of comment in forum
    # config: config dictionary
    feature_vector = []

    ## Semantic features (x52)

    # Question to Comment similarity (x1)
    q_cv = None
    for w in q_w:
        if q_cv is None:
            q_cv = model[w]
        else:
            q_cv += model[w]
    c_cv = None
    for w in c_w:
        if c_cv is None:
            c_cv = model[w]
        else:
            c_cv += model[w]
    if q_cv is not None and c_cv is not None:
        q_cv = [ float(x)/len(q_w) for x in q_cv ]
        c_cv = [ float(x)/len(c_w) for x in c_cv ]
        feature_vector.append(cosine(q_cv, c_cv))
    else:
        feature_vector.append(0)

    # Maximized similarity (x5)
    maxsims = [ 0.0 ] * 5
    for w in c_w:
        hq.heappush(maxsims, cosine(q_cv, model[w]))
        hq.heappop(maxsims)
    maxsims = sorted(maxsims, reverse=True)

    cntsim = 0
    sumsim = 0.0
    for sim in maxsims:
        cntsim += 1
        sumsim += sim
        avgsim = sumsim/cntsim
        feature_vector.append(avgsim)

    # Aligned similarity (x1)
    alisims = []
    for w_q in q_w:
        bestsim = 0.0
        for w_c in c_w:
            bestsim = max(bestsim, cosine(model[w_q], model[w_c]))
        alisims.append(bestsim)
    feature_vector.append(sum(alisims)/len(alisims))

    # Part of speech (POS) based word vector similarities (x45)
    path = config['POS_TAG']['path']
    classpath = path + config['POS_TAG']['jar']
    modelpath = path + config['POS_TAG']['model']
    tagger = StanfordPOSTagger(modelpath, classpath)
    config_java(options='-Xms4096M -Xmx4096M', verbose=False)

    global tagger_cache
    if tagger_cache.get(q_w) is None:
        tag_qw = tagger.tag(q_w)
        tagger_cache[q_w] = tag_qw
    else:
        tag_qw = tagger_cache[q_w]
    tag_cw = tagger.tag(c_w)

    dict_t = { 'q' : {}, 'c' : {} }
    for tag in POS_TAGS:
        dict_t['q'][tag] = [ None, 0 ]
        dict_t['c'][tag] = [ None, 0 ]
    for w_tag in tag_qw:
        dict_t['q'][w_tag[1]][1] += 1
        dict_t['q'][w_tag[1]][0] = auxAdd(dict_t['q'][w_tag[1]][0], model[w_tag[0]])
    for w_tag in tag_cw:
        dict_t['c'][w_tag[1]][1] += 1
        dict_t['c'][w_tag[1]][0] = auxAdd(dict_t['c'][w_tag[1]][0], model[w_tag[0]])
    for tag in POS_TAGS:
        if dict_t['q'][tag][1] == 0:
            feature_vector.append(0)
            continue
        if dict_t['c'][tag][1] == 0:
            feature_vector.append(0)
            continue
        avg_tq = [ float(x) / dict_t['q'][tag][1] for x in dict_t['q'][tag][0] ]
        avg_tc = [ float(x) / dict_t['c'][tag][1] for x in dict_t['c'][tag][0] ]
        feature_vector.append(cosine(avg_tq, avg_tc))

    # Word clusters (WC) similarity (SKIPPED)
    # LDA topic similarity (SKIPPED)

    ## Metadata features (x5)

    # Comment contains a question mark (x1)
    feature_vector.append(True in [ '?' in w for w in c_w ])

    # Comment length (x1)
    feature_vector.append(len(c_w))

    # Question length (x1)
    feature_vector.append(len(q_w))

    # Question to comment length (x1)
    feature_vector.append(float(len(c_w))/len(q_w))

    # Answer rank in the thread (x1)
    feature_vector.append(rank + 1)

    # Question and comment author same ? (SKIPPED)
    # Question category (SKIPPED)

    return feature_vector
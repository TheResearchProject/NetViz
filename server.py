import json
import MySQLdb
import datetime
import networkx
from flask import Flask, request

app=Flask(__name__)

#simply enter/change DB parameters
db_params=dict(host="localhost", user="root", passwd="", db="db", charset='utf8', use_unicode=True)

def get_data_from_db(newsitem=None, date_from=None, date_to=None, strip_by_date=False):
    # init db connection
    db=MySQLdb.connect(**db_params)
    
    # init vars
    nodes=[]
    links=[]
    node_index={}

    # make newsitems query
    query_type='single-item' if newsitem!=None else 'date-range'
    query="SELECT NewsItem.ID, NewsItem.Title, NewsItem.Date, Author.Name, "\
        "length(NewsItem.Content)-length(replace(NewsItem.Content, ' ', ''))+1 as WordCount "\
        "FROM NewsItem "\
        "INNER JOIN LinkingAuthors "\
        "ON NewsItem.ID=LinkingAuthors.NewsItemID "\
        "INNER JOIN Author "\
        "ON LinkingAuthors.AuthorID=Author.ID"
    if query_type=='date-range':
        query+=" WHERE NewsItem.Date>=%s and NewsItem.Date<=%s"
        params=(date_from, date_to)
    else:
        query+=" WHERE NewsItem.ID=%s"
        params=(int(newsitem),)
    query+=" ORDER BY NewsItem.ID"

    # fetch newsitems
    cur=db.cursor()
    cur.execute(query, params)
    node_rows=cur.fetchall()
    for row in node_rows:
        ID, Title, Date, Author, WordCount=row
        node_index_key='N%d'%ID
        if node_index_key not in node_index:
            nodes.append({'type': 'n', 'id': ID, 'title': Title, 'author': Author, 'date': Date.ctime(), 'wc': WordCount})
            node_index[node_index_key]=len(nodes)-1
        else:
            index=node_index[node_index_key]
            node=nodes[index]
            node['author']+=', '+Author

    # make comments query
    query="SELECT NewsItem.ID, Comment.ID, Comment.ParentID, Comment.Title, Comment.Date, Author.Name, "\
        "length(Comment.Content)-length(replace(Comment.Content, ' ', ''))+1 as WordCount "\
        "FROM Comment "\
        "INNER JOIN Author "\
        "ON Comment.AuthorID=Author.ID "\
        "INNER JOIN LinkingComments "\
        "ON Comment.ID=LinkingComments.CommentID "\
        "INNER JOIN NewsItem "\
        "ON LinkingComments.NewsItemID=NewsItem.ID"
    if query_type=='date-range':
        query+=" WHERE NewsItem.Date>=%s and NewsItem.Date<=%s"
        params=(date_from, date_to)
        if strip_by_date==True:
            query+=" and Comment.Date>=%s and Comment.Date<=%s"
            params+=(date_from, date_to)
    else:
        query+=" WHERE NewsItem.ID=%s"
        params=(int(newsitem),)
    query+=" ORDER BY Comment.ID"

    # fetch comments
    cur.execute(query, params)
    link_rows=cur.fetchall()
    for row in link_rows:
        NID, CID, PID, Title, Date, Author, WordCount=row
        nodes.append({'type': 'c', 'id': CID, 'title': Title, 'date': Date.ctime(), 'author': Author, 'wc': WordCount})
        node_index['C%d'%CID]=len(nodes)-1

    # create links
    for row in link_rows:
        NID, CID, PID, Title, Date, Author, WordCount=row
        try:
            source=node_index['C%d'%CID]
            target=node_index['%s%d'%(('N', NID) if PID==None else ('C', PID))]
        except KeyError:
            continue
        links.append({'source': source, 'target': target, 'date': Date.ctime()})

    # close db connection
    cur.close()
    db.close()

    # returs result
    return {'nodes': nodes, 'links': links}


@app.route('/data')
def data():
    # check params
    newsitem=request.args.get('newsitem', None)
    date_from=request.args.get('date_from', None)
    date_to=request.args.get('date_to', None)
    strip_by_date=request.args.get('strip_by_date', 'falce')=='true'
    if newsitem==None and (date_from==None or date_to==None):
        return json.dumps({'_type': 'error', 'message': 'invalid parameters'})
    date_from=datetime.datetime.strptime(date_from, '%m/%d/%Y') if date_from!=None else None
    date_to=datetime.datetime.strptime(date_to+' 23:59:59', '%m/%d/%Y %H:%M:%S') if date_to!=None else None

    res=get_data_from_db(newsitem, date_from, date_to, strip_by_date)
    return json.dumps(res)

@app.route('/graphinfo')
def graphinfo():
    # check params
    id1=request.args.get('id1', None)
    id2=request.args.get('id2', None)
    if id1==None or len(id1)==0 or id1[0].lower() not in ('n', 'c'):
        return json.dumps({'_type': 'error', 'message': 'invalid parameters'})

    # retrieve id of newsitem
    id_type=id1[0].lower()
    id_val=int(id1[1:])
    if id_type=='n':
        newsitem=id_val
    else:
        db=MySQLdb.connect(**db_params)
        cur=db.cursor()
        cur.execute("SELECT NewsItemID FROM LinkingComments WHERE LinkingComments.CommentID=%s", (id_val,))
        newsitem=cur.fetchone()
        cur.close()
        db.close()
        if newsitem==None:
            return json.dumps({'_type': 'error', 'message': 'newsitem not fount'})
        newsitem=int(newsitem[0])

    # retrieve graph data    
    graph_data=get_data_from_db(newsitem=newsitem)
    nodes=graph_data['nodes']
    links=graph_data['links']
    if len(nodes)==0 or nodes[0]['type']!='n':
        return json.dumps({'_type': 'error', 'message': 'newsitem not found correctly'})

    # create networkx graph
    g=networkx.Graph()
    g.add_nodes_from(range(len(nodes)))
    g.add_edges_from([(i['source'], i['target']) for i in links])

    # find index of id1 in nodes
    ni=0 if id_type=='n' else map(lambda n: n['id'], nodes).index(id_val, 1)

    # make result
    res={
        'newsitem': newsitem,
        'diameter': 0 if g.number_of_edges()==0 else networkx.diameter(g),
        'avg_shortest_path': 0 if g.number_of_edges()==0 else '%0.2f'%networkx.average_shortest_path_length(g),
        'avg_clustering': networkx.average_clustering(g),
        'distance': networkx.shortest_path_length(g, 0, ni),
        'degree': g.degree(ni),
    }

    # return json
    return json.dumps(res)
    


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)

_log=function() {
    // ugly log function! because console.log.apply methods wont work!
    var n=arguments.length;
    var a=arguments;
    if(n==0) return;
    else if(n==1) console.log(a[0]);
    else if(n==2) console.log(a[0], a[1]);
    else if(n==3) console.log(a[0], a[1], a[2]);
    else if(n==4) console.log(a[0], a[1], a[2], a[3]);
    else console.log(a);
    _log.last=a;
}

App=(function() {
    var App=function() {
        this.strip_by_date=false;
        this.selected_nodes=[];

        $('#load-btn').button().click(this.load.bind(this));
        $('#menu-btn')
            .button({ text: false, icons: { primary: "ui-icon-triangle-1-s" } })
            .click(function() { $('#menu').show().focus(); });
        $('#menu').menu().position({
            my: 'left top',
            at: 'left bottom',
            of: $('#menu-btn')
        }).hide().blur(function() { $('#menu').hide(); });
        $('#menu').on('menuselect', this.on_menu.bind(this));
        $('#date_from').datepicker().val('01/10/2013');
        $('#date_to').datepicker().val('01/12/2013');
        $('#date-range-form').show();
    }

    App.prototype.on_menu=function(event, ui) {
        $('#menu').hide();
        var menu_item=ui.item.attr('menu-item');
        if(menu_item=='date-range') {
            $('#single-item-form').hide();
            $('#date-range-form').show();
        }
        else if(menu_item=='single-item') {
            $('#date-range-form').hide();
            $('#single-item-form').show();
        }
        else if(menu_item=='strip-by-date') {
            var s=ui.item.children().text();
            if(s.indexOf('[ ]')!=-1) {
                s=s.replace('[ ]', '[x]');
                this.strip_by_date=true;
            }
            else {
                s=s.replace('[x]', '[ ]');
                this.strip_by_date=false;
            }
            ui.item.children().text(s);
        }
    }

    App.prototype.load=function() {
        if($('#date-range-form').is(':visible')) {
            var date_from=$('#date_from').val();
            var date_to=$('#date_to').val();
            if(date_from=='' || date_to=='') {
                alert('please enter "from" and "to" dates')
                return
            }
            var params={date_from: date_from, date_to: date_to, strip_by_date: this.strip_by_date};
        }
        else {
            var newsitem=$('#newsitem').val();
            var re=/^\d+$/;
            if(!re.test(newsitem)) {
                alert('please enter a valid newsitem id')
                return
            }
            var params={newsitem: newsitem}
        }
        var self=this;
        $('body').css('cursor', 'wait');
        $.get('/data', params, function(r) {
            $('body').css('cursor', 'auto');
            var res=JSON.parse(r);
            if(res._type=='error') {
                alert(res.message);
                return;
            }
            self.graph=res;
            self.load_to_graph();
        });
    }
    
    App.prototype.load_to_graph=function() {
        var self=this;
        var color=d3.scale.category20();
        
        $('#main-graph-box').remove();
        $('<div id="main-graph-box"/>').appendTo('#graph-container');
        
        var width=$('#main-graph-box').width();
        var height=$('#main-graph-box').height();

        var rescale=function() {
                trans=d3.event.translate;
                scale=d3.event.scale;
                vis.attr("transform", "translate(" + trans + ")" + " scale(" + scale + ")");
        }

        var outer=d3.select("#main-graph-box")
            .call(d3.behavior.zoom().on("zoom", rescale))
            .on("dblclick.zoom", null)
            .append("svg:svg")
            .attr("width", width)
            .attr("height", height)
            .attr("pointer-events", "all");
        var vis=outer.append('svg:g')
            .append('svg:g')
        var force=d3.layout.force()
            .charge(-200)
            .linkDistance(30)
            .size([width, height])
            .nodes(this.graph.nodes)
            .links(this.graph.links)
            .start();
        var link=vis.selectAll(".link")
            .data(this.graph.links)
            .enter().append("line")
            .attr("class", "link");
        var node=vis.selectAll(".node")
            .data(this.graph.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", function(d) { return d.type=='n' ? 12 : 6; })
            .style("fill", function(d) { return color(d.id); })
            .call(force.drag)
            .on('mouseup', this.node_on_mouseup.bind(this));
        node.append("title").text(function(d) { return 'Id' + d.ID + 'Title: ' + d.title + '\nAuthor: ' + d.author + '\nWordcount: ' + d.wc });
        link.append("title").text(function(d) { return d.date; });
        force.on("tick", function() {
            link.attr("x1", function(d) { return d.source.x; })
                .attr("y1", function(d) { return d.source.y; })
                .attr("x2", function(d) { return d.target.x; })
                .attr("y2", function(d) { return d.target.y; });
            node.attr("cx", function(d) { return d.x; })
                .attr("cy", function(d) { return d.y; });
        });

    }

    App.prototype.node_on_mouseup=function(d) {
        var self=this;
        var i=this.selected_nodes.indexOf(d);
        if(i==-1) {
            this.selected_nodes.push(d);
            if(this.selected_nodes.length>1) {
                this.selected_nodes.shift();
            }
        }
        else {
            this.selected_nodes.splice(i, 1);
        }
        d3.selectAll('.node').classed("selected-node", function(d) { return self.selected_nodes.indexOf(d)!=-1; });

        var ids=this.selected_nodes.map(function(d) { return d.type+d.id; });
        if(ids.length==0) {
            return;
        }
        var params={id1: ids[0], id2: ids[1]}
        $.get('/graphinfo', params, this.set_graph_info_values.bind(this));
    }

    App.prototype.set_graph_info_values=function(r) {
        var res=JSON.parse(r);
        if(res._type=='error') {
            alert(res.message);
            return;
        }
        var info=res;
        $('#info-box [name=id]').text(info.newsitem);
        $('#info-box [name=diameter]').text(info.diameter);
        $('#info-box [name=avg-shortest-path]').text(info.avg_shortest_path);
        $('#info-box [name=avg-clustering]').text(info.avg_clustering);
        $('#info-box [name=distance]').text(info.distance);
        $('#info-box [name=degree]').text(info.degree);
    }
    
    App.prototype.toString=function() {
        return '<app object>';
    }
    
    return App;
})();

$(function() {
    app=new App();
});

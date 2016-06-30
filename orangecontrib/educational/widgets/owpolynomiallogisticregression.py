from Orange.data import Table, ContinuousVariable, Table, Domain
from Orange.widgets import highcharts, settings, gui
from Orange.widgets.utils.owlearnerwidget import OWBaseLearner
from Orange.classification import LogisticRegressionLearner, Learner
import numpy as np
from math import log
from PyQt4.QtGui import QSizePolicy

class Scatterplot(highcharts.Highchart):
    """
    Scatterplot extends Highchart and just defines some sane defaults:
    * enables scroll-wheel zooming,
    * enables rectangle (+ individual point) selection,
    * sets the chart type to 'scatter' (could also be 'bubble' or as
      appropriate; Se Highcharts JS docs)
    * sets the selection callback. The callback is passed a list (array)
      of indices of selected points for each data series the chart knows
      about.
    """

    paint_function = """
        paint_function = function() {
            console.log("a");
            $('#belowPath').remove()
            $('#abovePath').remove()

            var series = chart.series[0];
            var path = [];

            series.data.forEach(function(element) {
                path.push(element.plotX + chart.plotLeft);
                path.push(element.plotY + chart.plotTop);
            });

            var path_above = ['M', chart.plotLeft, chart.plotTop, 'L']
                .concat(path)
                .concat([chart.plotLeft + chart.plotWidth, chart.plotTop]);

            var path_below = ['M', chart.plotLeft, chart.plotTop + chart.plotHeight, 'L']
                .concat(path)
                .concat([chart.plotLeft + chart.plotWidth, chart.plotTop + chart.plotHeight]);

            chart.renderer.path(path_above)
                .attr({
                    stroke: "none",
                    fill: chart.series[1].color,
                    'fill-opacity': 0.2,
                    zIndex: 0.5,
                    id: "abovePath"
                }).add();

            chart.renderer.path(path_below)
                .attr({
                    stroke: "none",
                    fill: chart.series[2].color,
                    'fill-opacity': 0.2,
                    zIndex: 0.5,
                    id: "belowPath"
                }).add();
        }
        """

    def __init__(self, **kwargs):
        super().__init__(enable_zoom=True,
                         bridge=self,
                         enable_select='',
                         chart_type='scatter',
                         plotOptions_series_cursor="move",
                         **kwargs)
        self.evalJS(self.paint_function)


class OWPolyinomialLogisticRegression(OWBaseLearner):
    name = "Polynomial classification"
    description = "a"  #TODO: description
    icon = "icons/mywidget.svg"
    want_main_area = True
    resizing_enabled = True

    # inputs and outputs
    inputs = [("Data", Table, "set_data"),
              ("Learner", Learner, "set_learner")]

    data = None
    selected_data = None

    LEARNER = LogisticRegressionLearner
    learner_name = settings.Setting("Univariate Classification")

    # selected attributes in chart
    attr_x = settings.Setting('')
    attr_y = settings.Setting('')

    graph_name = 'scatter'

    def add_main_layout(self):
        # options box
        self.optionsBox = gui.widgetBox(self.controlArea, "Options")
        self.cbx = gui.comboBox(self.optionsBox, self, 'attr_x',
                                label='X:',
                                orientation='horizontal',
                                callback=self.refresh,
                                sendSelectedValue=True)
        self.cby = gui.comboBox(self.optionsBox, self, 'attr_y',
                                label='Y:',
                                orientation='horizontal',
                                callback=self.refresh,
                                sendSelectedValue=True)
        self.cbx.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))
        self.cby.setSizePolicy(QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed))

        gui.rubber(self.controlArea)

        # plot
        self.scatter = Scatterplot(Axis_gridLineWidth=0,
                                   yAxis_gridLineWidth=0,
                                   title_text='',
                                   tooltip_shared=False,
                                   debug=True)  # TODO: set false when end of development
        # Just render an empty chart so it shows a nice 'No data to display'
        self.scatter.chart()
        self.mainArea.layout().addWidget(self.scatter)

    def set_learner(self, learner):
        self.LEARNER = learner
        self.change_features()

    def set_data(self, data):
        """
        Function receives data from input and init part of widget if data are ok. Otherwise set empty plot and notice
        user about that
        :param data: input data
        :type data: Orange.data.Table or None
        """
        self.data = data

        def reset_combos():
            self.cbx.clear()
            self.cby.clear()

        def init_combos():
            """
            function initialize the combos with attributes
            """
            reset_combos()
            for var in data.domain if data is not None else []:
                if var.is_primitive() and var.is_continuous:
                    self.cbx.addItem(gui.attributeIconDict[var], var.name)
                    self.cby.addItem(gui.attributeIconDict[var], var.name)

        self.warning(1)  # remove warning about too less continuous attributes if exists
        self.warning(2)  # remove warning about not enough data

        if data is None or len(data) == 0:
            reset_combos()
            self.set_empty_plot()
        elif sum(True for var in data.domain.attributes if isinstance(var, ContinuousVariable)) < 2:
            reset_combos()
            self.warning(1, "Too few Continuous feature. Min 2 required")
            self.set_empty_plot()
        elif data.domain.class_var is None:
            reset_combos()
            self.warning(1, "No class provided")
            self.set_empty_plot()
        elif len(data.domain.class_var.values) > 2:
            reset_combos()
            self.warning(1, "Too much classes. Max 2 required")
            self.set_empty_plot()
        else:
            init_combos()
            self.attr_x = self.cbx.itemText(0)
            self.attr_y = self.cbx.itemText(1)
            self.change_features()

    def set_empty_plot(self):
        self.scatter.clear()

    def refresh(self):
        if self.data is not None:
            self.change_features()

    def change_features(self):

        self.selected_data = self.concat_x_y()
        self.replot()

    def replot(self):
        """
        This function performs complete replot of the graph without animation
        """
        attr_x, attr_y = self.data.domain[self.attr_x], self.data.domain[self.attr_y]
        data_x = [v[0] for v in self.data[:, attr_x]]
        min_x = min(data_x)
        max_x = max(data_x)
        diff = max_x - min_x
        min_x = min_x - 0.03 * diff
        max_x = max_x + 0.03 * diff
        model = self.LEARNER(self.selected_data)

        # plot centroids
        options = dict(series=[])

        line_series = self.plot_line(model, min_x, max_x)
        options['series'].append(line_series)

        # make sure that series[1] are train data of the class above the line and series[2] data below the line
        if model(line_series["data"][0] + np.array([0, 1]))[0] == 1:
            # model called with point that is for sue above the line
            classes = [1, 0]
        else:
            classes = [0, 1]

        options['series'] += [dict(data=[list(p.attributes())
                                            for p in self.selected_data if int(p.get_class()) == _class],
                                   type="scatter",
                                   zIndex=10,
                                   showInLegend=False) for _class in classes]

        # highcharts parameters
        kwargs = dict(
            xAxis_title_text=attr_x.name,
            yAxis_title_text=attr_y.name,
            xAxis_min=min_x,
            xAxis_max=max_x,
            chart_events_redraw="/**/paint_function/**/",
            tooltip_headerFormat="",
            tooltip_pointFormat="<strong>%s:</strong> {point.x:.2f} <br/>"
                                "<strong>%s:</strong> {point.y:.2f}" %
                                (self.attr_x, self.attr_y))
        # plot
        self.scatter.chart(options, **kwargs)
        self.scatter.evalJS("chart.redraw()")

    def plot_line(self, model, x_from, x_to):
        # min and max x

        if self.LEARNER.name == "logreg":

            thetas = model.coefficients
            intercept = model.intercept
            line_function = lambda x: - (log(1) + thetas[0, 0] * x + intercept) / thetas[0, 1]
            xs = np.linspace(x_from, x_to)
            ys = line_function(xs)
            return dict(data=np.hstack((xs[:, None], ys[:, None])).tolist(),
                        type="line",
                        showInLegend=False,
                        marker=dict(enabled=False),
                        enableMouseTracking=False)
        else:
            return {}

    def concat_x_y(self):
        """
        Function takes two selected columns from data table and merge them in new Orange.data.Table
        :return: table with selected columns
        :type: Orange.data.Table
        """
        attr_x, attr_y = self.data.domain[self.attr_x], self.data.domain[self.attr_y]
        cols = []
        for attr in (attr_x, attr_y):
            subset = self.data[:, attr]
            cols.append(subset.Y if subset.Y.size else subset.X)
        x = np.column_stack(cols)
        domain = Domain([attr_x, attr_y], self.data.domain.class_var)
        return Table(domain, x, self.data.Y)

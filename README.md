# ballbotCommander
Python Serial Grapher for Debugging Visualisation

Requires PyQt4, pyqtgraph, pyopengl, and python 3.x

Current features:
 - Select which variables you wish to plot from legend
 	 - Save and load legends
 - Separation of plot data from user readable data using '$'
 - High performance plotting at >30Hz.
 - Multithreading using QThread

Performance is much better than serialGraph (an older but more lightweight app I made for similar purposes).
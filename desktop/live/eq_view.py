"""Small monochrome EQ view; 64 response points, redrawn only on edits."""
import math
import cmath
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QPolygonF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QDial, QDoubleSpinBox
from eq import DEFAULT, coefficients

BANDS=(('low_db','Bass'),('mid_db','Mid'),('high_db','Treble'))

def response_db(settings, count=64, rate=48000):
    """Portable algorithm: log-frequency samples of the three biquad responses."""
    coeffs=[coefficients(b,settings[b+'_hz'],settings[b+'_db'],settings['mid_q'],rate)
            for b in ('low','mid','high')]
    result=[]
    for i in range(count):
        hz=20*(1000**(i/(count-1)))
        z=cmath.exp(-2j*math.pi*hz/rate)
        gain=1.
        if settings['enabled']:
            for b0,b1,b2,a1,a2 in coeffs:
                gain*=abs((b0+b1*z+b2*z*z)/(1+a1*z+a2*z*z))
        result.append(20*math.log10(max(gain,1e-12)))
    return result

class EQCurve(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(280,130)
        self.setMaximumHeight(190)
        self.setAccessibleName('EQ frequency response')
        self.setToolTip('Tone curve: bass on the left, treble on the right. Not an audio spectrum.')
        self.set_settings(DEFAULT)

    def set_settings(self,settings):
        self.points=response_db(settings)
        self.update()

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.fillRect(self.rect(),QColor('#151a1d'))
        left,top,right,bottom=38,16,self.width()-12,self.height()-28
        middle=(top+bottom)/2
        painter.setPen(QColor('#818b90'))
        painter.drawText(4,top+5,'+24')
        painter.drawText(16,int(middle)+4,'0')
        painter.drawText(4,bottom+4,'−24')
        painter.drawLine(left,int(middle),right,int(middle))
        for fraction,label in ((0,'20'),(1/3,'200'),(2/3,'2k'),(1,'20k')):
            x=int(left+fraction*(right-left))
            painter.drawLine(x,top,x,bottom)
            painter.drawText(x-10,bottom+19,label)
        painter.setPen(QPen(QColor('#f1f4f5'),2))
        points=QPolygonF([QPointF(left+i*(right-left)/(len(self.points)-1),
                     middle-max(-24,min(24,db))*(bottom-top)/48)
                     for i,db in enumerate(self.points)])
        painter.drawPolyline(points)

class ToneKnob(QWidget):
    def __init__(self,label,changed,minimum=-12,maximum=12,suffix=' dB',decimals=1):
        super().__init__()
        layout=QVBoxLayout(self)
        title=QLabel(label)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.dial=QDial()
        self.scale=10**decimals
        self.dial.setRange(round(minimum*self.scale),round(maximum*self.scale))
        self.dial.setNotchesVisible(True)
        self.dial.setFixedSize(100,100)
        self.dial.setAccessibleName(label)
        layout.addWidget(self.dial,alignment=Qt.AlignmentFlag.AlignCenter)
        self.spin=QDoubleSpinBox()
        self.spin.setRange(minimum,maximum)
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(1/self.scale)
        self.spin.setSuffix(suffix)
        self.spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin.setAccessibleName(label+' gain')
        layout.addWidget(self.spin)
        self.changed=changed
        self.dial.valueChanged.connect(lambda value:self.edit(value/self.scale))
        self.spin.valueChanged.connect(self.edit)

    def setValue(self,value):
        from PySide6.QtCore import QSignalBlocker
        blockers=[QSignalBlocker(self.spin),QSignalBlocker(self.dial)]
        self.spin.setValue(value)
        self.dial.setValue(round(value*self.scale))
        del blockers

    def edit(self,value):
        self.setValue(value)
        self.changed(value)

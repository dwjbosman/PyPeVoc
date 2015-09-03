#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  PVanalyse.py
#
#  Do a Phase vocoder decomposition of a signal into its quasi-sinusoidal
# components
#  
#  Copyright 2015 Andre Almeida <andre.almeida@univ-lemans.fr>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  

import numpy as np
import pylab as pl

from PeakFinder import PeakFinder as pf

"""  
Perform the Phase vocoder decomposition of a signal into 
quasi-sinusoidal components
"""

pi2 = 2.0*np.pi

# approximate formulas for logarithmic ratios

# 20*log10(rat) approx= dbconst*(rat-1)
dbconst = 20./np.log(10)
# 12*log2(rat) approx= dfconst*(rat-1)
dfconst = 12./np.log(2)

def dpitch2st_exact(f1,f2):
    '''
    Convert a frequency interval to semitones
    '''
    return 12*np.log2(float(f2)/f1)

def dpitch2st(f1,f2):
    '''
    Convert a frequency interval between f1 and f2 to semitones
    (aprroximate formula for nearby freq.
     for exact formula use dpitch2st_exact(f1,f2))
    '''
    return 17.312*(float(f2)/f1-1.0)
    

class PV:
    def __init__(self, x, sr, nfft=1024, hop=None, npks=20, pkthresh=0.005, wind=np.hanning):
        '''
        Phase vocoder object.
        Arguments:
            * sr   = Sampling rate
            * nfft = Number of points in FFT analysis window
            * hop  = Number of points between FFT windows
            * npks = Maximum number of peaks at each frame
            * pkthresh = Threshold of peak amplitude relative of maximum
        '''
        
        self.x = np.array(x)
        self.nsamp = len(self.x)
        self.sr   = sr
        self.nfft = nfft
        self.nfft2 = nfft/2
        if hop is None:
            self.hop = self.nfft/2
        else:
            self.hop  = hop
        self.peakthresh = pkthresh
        self.npeaks = npks
        self.nframes = 0
        
        self.win = wind(nfft)
        self.wsum = sum(self.win)
        self.wsum2 = sum(self.win**2)
        #self.wfact = self.wsum#*np.sqrt(self.nfft);
        #I don't remember why this is the normalisation factor...
        self.wfact = np.sqrt(self.wsum2*self.nfft)/2.0
        
        # the freqency step between bins
        self.fstep = float(self.sr)/float(self.nfft)
        
        # time difference beween frames
        self.dt = float(self.hop)/float(self.sr)
        
        # multiples of 2pi
        #self.all2pi = 2*np.pi*np.arange(0:round(self.hop/2.0))
        
        # central freq of each bin
        self.fbin = np.arange(float(nfft))*self.fstep
        # pase difference between frames for each bin
        dthetabin = pi2*self.fbin*self.dt
        # wrapping factor for each bin * 2pi
        self.wfbin = np.round(dthetabin/pi2) * pi2
        
        # storage for the older fft frame
        self.oldfft = np.zeros(self.nfft2)
        
        # calculated values
        self.t  = []
        self.f  = []
        self.ph = []
        self.mag= []
        
    def dphase2freq(self, dph, nbin):
        '''
        Calculates the "instantaneous frequency" corresponding to the 
        phase difference dph between two consecutive frames
        '''
        # Unwrapped phase
        #dphw=dph + self.wfbin[nbin] + np.array([-pi2,0,pi2])
        dphw=dph + self.wfbin[nbin] + pi2*np.arange(-1,2)
        # precise frequency options
        freq = dphw / self.dt / pi2
        # search among neighboring bins for the right freq
        ii = np.argmin(abs(self.fbin[nbin]-freq))
        return freq[ii]
        #return self.fbin[nbin]
        
    def calc_fft_frame(self, pos):
        '''
        Calculate a FFT frame at pos
        '''
        
        thisx = self.x[pos:pos+self.nfft]
        xw = thisx*self.win
        fx = np.fft.fft(xw) / self.wfact
        return fx
    
    def calc_pv_frame(self,pos):
        '''
        Determine PV peaks and calculate frequencies 
        based on previous fft frame
        '''
        
        wd=1
        
        fxa = self.calc_fft_frame(pos)
        fx = fxa[:self.nfft2]
        
        frat = fx / self.oldfft
        
        famp = abs(fx)
        # find the peaks in the FFT
        pkf = pf(famp, npeaks = self.npeaks,minrattomax=self.peakthresh)
        pkf.boundaries()
        pkf.filter_by_salience(rad=5)
        pk = pkf.get_pos()
        
        f=[]
        mag=[]
        ph=[]
        
        # for each peak
        for ipk, nbin in enumerate(pk):
            thisph = np.angle(fx[nbin])
            # pahse difference
            dph = np.angle(frat[nbin])
            freq = self.dphase2freq(dph,nbin)
                
            if freq > 0.0:
                f.append(freq)
                # amplitude
                imin = max(nbin-wd,1)
                imax = min(nbin+wd,len(famp))
                mag.append(np.sqrt(sum(famp[imin:imax+1]**2)))
                #mag.append(np.sqrt(pkf.calc_individual_area(ipk,funct=lambda x:x*x)))
                
                ph.append(thisph)
            
        self.oldfft = fx
        return f, mag, ph
        
    def run_pv(self):
        
        allf=[]
        allmag=[]
        allph=[]
        t=[]
        
        curpos = 0
        maxpos = self.nsamp - self.nfft
        while curpos < maxpos:
            f = np.zeros(self.npeaks)
            mag = np.zeros(self.npeaks)
            ph = np.zeros(self.npeaks)
            
            ff, magf, phf = self.calc_pv_frame(curpos)
            
            f[0:len(ff)]=ff
            mag[0:len(magf)]=magf
            ph[0:len(phf)]=phf
            
            allf.append(f)
            allmag.append(mag)
            allph.append(ph)
            
            t.append((curpos+self.nfft/2.0)/self.sr)
            
            curpos += self.hop
        
        self.f = np.array(allf)
        self.mag = np.array(allmag)
        self.ph = np.array(allph)
        #time values
        self.t = np.array(t)
        self.nframes = len(t)
    
    def toSinSum(self, maxpitchjmp = 0.5):
        '''
        Convert to Sine sum
        Arguments:
            * maxpitchjmp = maximum allowed jump in pitch between frames 
                            (in semitones)
        '''
        ss = SinSum(self.sr, nfft=self.nfft, hop=self.hop)
        
        #lastf     = np.zeros(self.npeaks)
        #lastssidx = np.nan*np.zeros(self.npeaks)
        
        for fr in range(self.nframes):
            # process new peaks in decreasing magnitude
            # irev = np.argsort(self.mag[fr,:])
            # idx = irev[::-1]
            # ffr = self.f[fr,idx]
            # mfr = self.mag[fr,idx]
            # pfr = self.ph[fr,idx]
            # for f,mag,ph in zip(ffr,mfr,pfr):
            #     ss.add_point(fr,f,mag,ph,maxpitchjmp=maxpitchjmp)
            ss.add_frame(fr,self.f[fr,:],self.mag[fr,:],self.ph[fr,:])
        return ss
        
    def plot_time_freq(self, colors=True):
        import pylab as pl
        
        pl.figure()
        # make time matrix same shape as others
        t = np.outer(self.t,np.ones(self.npeaks))
        f = self.f
        if colors:
            mag = 20*np.log10(self.mag)
            pl.scatter(t,f,s=6,c=mag,lw=0)
        else:
            mag = 100+20*np.log10(self.mag)
            pl.scatter(t,f,s=mag,lw=0)
        pl.xlabel('Time (s)')
        pl.ylabel('Frequency (Hz)')
        if colors:
            cs=pl.colorbar()
            cs.set_label('Magnitude (dB)')
        pl.show()

    def plot_time_mag(self):
        import pylab as pl
        
        pl.figure()
        t = np.outer(self.t,np.ones(self.npeaks))
        #f = np.log2(self.f)
        f=self.f
        mag = 20*np.log10(self.mag)
        pl.scatter(t,mag,s=10,c=f,lw=0,norm=pl.matplotlib.colors.LogNorm())
        pl.xlabel('Time (s)')
        pl.ylabel('Magnitude (dB)')
        cs=pl.colorbar()
        cs.set_label('Frequency (Hz)')
        pl.show()
        
    def get_time_vector(self):
        return self.t
        
    def get_sample_vector(self):
        return (self.t*self.sr).astype('int')

class PVHarmonic(PV):
    def __init__(self,*args,**kwargs):
        self.fmin = 30.0
        PV.__init__(self,*args,**kwargs)
        
    def set_f0(self, f0, t=None):
        '''
        Assign a f0 vector to the search
        Argument:
            * f0: f0 vector over time
            * t: if present, values of time corresponding to f0
                 otherwise, the tie values correspond to the hop size
        '''
        
        # internal time vector
        tint = np.arange(round(self.hop+self.nfft/2),len(self.x),self.hop)/float(self.sr)
        
        if t is None:
            self.f0 = f0
        else:
            self.f0 = np.interp(tint,t,f0)

    def calc_pv_frame(self,pos,f0):
        '''
        Determine PV peaks and calculate frequencies 
        based on previous fft frame
        '''
        
        wd=1
        
        fxa = self.calc_fft_frame(pos)
        fx = fxa[:self.nfft2]
        
        frat = fx / self.oldfft
        
        famp = abs(fx)
        
        f=[]
        mag=[]
        ph=[]
        
        # for each f0 multiple
        f0bin = f0/self.sr*self.nfft
        bins = np.round(np.arange(f0bin,self.nfft2-1,f0bin))
        for ipk, nbin in enumerate(bins):
            if ipk>0:
                if f[0] > self.fmin:
                    corrbin = f[0]/self.sr*self.nfft*(ipk+1)
                    if corrbin < self.nfft2-1:
                        nbin = int(round(corrbin))
                        #print nbin
            
            thisph = np.angle(fx[nbin])
            # pahse difference
            dph = np.angle(frat[nbin])
            freq = self.dphase2freq(dph,nbin)
            #freq = ipk*f0
                

            f.append(freq)
            # amplitude
            imin = max(nbin-wd,1)
            imax = min(nbin+wd,len(famp))
            mag.append(np.sqrt(sum(famp[imin:imax+1]**2)))
            #mag.append(np.sqrt(pkf.calc_individual_area(ipk,funct=lambda x:x*x)))
            
            ph.append(thisph)
            
        self.oldfft = fx
        return f, mag, ph
        
    def run_pv(self):
        
        allf=[]
        allmag=[]
        allph=[]
        t=[]
        
        curpos = 0
        maxpos = self.nsamp - self.nfft
        while curpos < maxpos:
            f = np.zeros(self.npeaks)
            mag = np.zeros(self.npeaks)
            ph = np.zeros(self.npeaks)
            
            ff, magf, phf = self.calc_pv_frame(curpos,self.f0[int((curpos)/self.hop)])
            
            nh = min(len(ff),len(f))
            
            f[0:nh]=ff[0:nh]
            mag[0:nh]=magf[0:nh]
            ph[0:nh]=phf[0:nh]
            
            allf.append(f)
            allmag.append(mag)
            allph.append(ph)
            
            t.append((curpos+self.nfft/2.0)/self.sr)
            
            curpos += self.hop
        
        self.f = np.array(allf)
        self.mag = np.array(allmag)
        self.ph = np.array(allph)
        #time values
        self.t = np.array(t)
        self.nframes = len(t)


        
class Partial(object):
    def __init__(self,pdict=None):
        '''
        A quasi-sinusoidal partial
        Arguments: pdict with:
            * pdict['t'] = time array
            * pdict['f'] = frequency array
            * pdict['mag'] = magnitude array
            * pdict['ph'] = phase array
        '''
        
        if pdict is None:
            self.t  = []
            self.f  = []
            self.mag= []
            self.ph = []
        else:
            self.t  = pdict['t']
            self.f  = pdict['f']
            self.mag= pdict['mag']
            self.ph = pdict['ph']
            
        
    def add_point(self,t,f,mag,ph):
        '''
        Append a single point in the partial
        '''
        if t>max(self.t):
            self.t.append(t)
            self.f.append(f)
            self.mag.append(mag)
            self.ph.append(ph)
        else:
            idx = (self.t>t).index(True)
            self.t.insert(idx,t)
            self.f.insert(idx,f)
            self.mag.insert(idx,mag)
            self.ph.insert(idx,ph)
            
    def synth(self, sr):
        '''
        Resynthesise the sinusoidal partial at sampling rate sr
        '''
        
class RegPartial(object):
    def __init__(self,istart,pdict=None):
        '''
        A quasi-sinusoidal partial with homogeneous sampling
        Arguments: 
          istart = starting index
          pdict with:
            * pdict['t'] = time array
            * pdict['f'] = frequency array
            * pdict['mag'] = magnitude array
            * pdict['ph'] = phase array
        '''
        
        self.start_idx = istart
        
        if pdict is None:
            self.f  = []
            self.mag= []
            self.ph = []
        else:
            self.f  = pdict['f']
            self.mag= pdict['mag']
            self.ph = pdict['ph']
            
        
    def append_point(self,f,mag,ph):
        '''
        Add a single point to the end of partial
        '''
        self.f.append(f)
        self.mag.append(mag)
        self.ph.append(ph)

    def prepend_point(self,f,mag,ph):
        '''
        Add a single point to the start of partial
        '''
        self.f.insert(0,f)
        self.mag.insert(0,mag)
        self.ph.insert(0,ph)
        self.start_idx -= 1
            
            
    def get_freq_at_frame(self,fr):
        
        relidx = fr - self.start_idx
        
        if relidx>=0:
            return self.f[relidx]
        else:
            return np.nan

    def get_mag_at_frame(self,fr):
        
        relidx = fr - self.start_idx
        
        if relidx>=0:
            return self.mag[relidx]
        else:
            return np.nan

        
    def synth(self, sr, hop):
        '''
        Resynthesise the sinusoidal partial at sampling rate sr
        '''
        
        # reference phase
        iref  = np.argmax(self.mag)
        phref = self.ph[iref]
        #reference sample
        sref = (iref+1)*hop
        
        # time corresponding to frames
        tfr = (self.start_idx - 1 + np.arange(len(self.f)+2)) * float(hop)/sr
        ffr = self.f
        ffr=np.insert(ffr,0,ffr[0])
        ffr=np.append(ffr,ffr[-1])
        mfr = self.mag
        mfr=np.insert(mfr,0,0.0)
        mfr=np.append(mfr,0.0)
        
        # start synth one frame before and one after to avoid dicontinuites
        tmin = min(tfr)-hop/sr
        tmax = max(tfr)+hop/sr
        
        # time of samples
        t   = np.arange(round(tmin*sr),round(tmax*sr))/sr
        f   = np.interp(t,tfr,ffr)
        mag = np.interp(t,tfr,mfr)
        
        ph = np.cumsum(2*np.pi*f/sr)
        ph = ph-ph[sref]+phref
        
        return mag * np.cos(ph), (self.start_idx - 1)*hop
        
class SinSum(object):
    def __init__(self, sr, nfft=1024, hop=512):
        '''
        Sine sum object:
        Represents a sound decomposed in a sum of quasi-sine waves,
        in which amplitude and frequency vary slowly in time
        Arguments:
            * sr   = Sampling rate
            * nfft = Number of points in FFT analysis window
            * hop  = Number of points between FFT windows
        '''
        
        # sine component structure
        self.partial = []
        
        # store start and end values for faster search
        self.st=[]
        self.end=[]
        self.nfft = nfft
        self.hop = hop
        self.sr = sr
    
    def add_empty_partial(self,idx):
        '''
        Append an empty partial at frame idx 
        '''
        
        newpart = RegPartial(idx)
        self.partial.append(newpart)
        self.st.append(idx)
        self.end.append(idx)
        
        return newpart
        
    def add_point(self, fr, f, mag, ph, maxpitchjmp = 0.5):
        '''
        Add a point to the matching partial or create a new one 
        Slow! Use add_frame, to add all the peak values 
        '''
        
        #partials = self.get_partials_at_frame(fr-1)
        pidx = self.get_partials_idx_ending_at_frame(fr-1)
        #tidx = self.get_partials_idx_at_frame(fr)
        #pidx = np.setdiff1d(pidx,tidx,assume_unique=True)
        
        
        if len(pidx) > 0:
            pmag = [self.partial[ii].get_mag_at_frame(fr-1) for ii in pidx]
            
            # zips, sorts and unzips
            pmag, pidx = zip(*sorted(zip(pmag,pidx),reverse=True))
            partials = [self.partial[ii] for ii in pidx]
            prev_f = [pp.get_freq_at_frame(fr-1) for pp in partials]
            
            stonediff = np.array([abs(dpitch2st(ff,f)) for ff in prev_f])
            dbdiff = 20*np.log10(np.array(pmag)/mag)
            # partials should be near in frequency and magnitude
            ovdiff = stonediff+abs(dbdiff)
            nearest = np.argmin(ovdiff)
        
            if stonediff[nearest] < maxpitchjmp:
                idx = pidx[nearest]
                part = partials[nearest]
            else:
                part = self.add_empty_partial(fr)
                idx = -1
        else:
            part = self.add_empty_partial(fr)
            idx = -1
        
        part.append_point(f,mag,ph)
        self.end[idx] = fr
        
    def add_frame(self, fr, f, mag, ph, maxpitchjmp = 0.5):

        # process new peaks in decreasing magnitude
        irev = np.argsort(mag)
        idx = irev[::-1]
        idx=idx[np.logical_and(f[idx]>0,mag[idx]>0)]
        fsrt = f[idx]
        msrt = mag[idx]
        psrt = ph[idx]

        #partials = self.get_partials_at_frame(fr-1)
        pidx = self.get_partials_idx_ending_at_frame(fr-1)
        # if there are some previous partials...
        if len(pidx)>0:
            pmag = [self.partial[ii].get_mag_at_frame(fr-1) for ii in pidx]
            allpmagl, pidx = zip(*sorted(zip(pmag,pidx),reverse=True))
           
            allpidx = np.array(pidx)
            allpmag = np.array(allpmagl)
        
            allpartials = [self.partial[ii] for ii in allpidx]
            allpf = np.array([pp.get_freq_at_frame(fr-1) for pp in allpartials])
            unused = np.ones_like(allpidx,dtype=bool)
        
        
        
        
            for fc,mc,pc in zip(fsrt,msrt,psrt):
                # select old partials 
                pidx = allpidx[unused]
                #print 'unused: %d, len: %d\n'%(sum(unused),len(pidx))
            
                # if pidx is not empty...
                if len(pidx)>0:
                    #print 'Checking previous..'
                    pmag = allpmag[unused]
                    pf = allpf[unused]
                
                    stonediff = abs(dpitch2st(pf,fc))
                    #dbdiff = 20*np.log10(pmag/mc)
                    # very rough formula for db:
                    dbdiff = dbconst*(pmag/mc-1)
            
                    ovdiff = stonediff+abs(dbdiff)
                    nearest = np.argmin(ovdiff)
                    #print 'Distance: %f'%(ovdiff[nearest])
            
                    if stonediff[nearest] < maxpitchjmp:
                        
                        idx = pidx[nearest]
                        part = self.partial[idx]
                        unused[nearest]=False
                    else:
                        part = self.add_empty_partial(fr)
                        idx = -1
                # if no more previous partials left (pidx is empty)
                # add a new partial
                else:
                    part = self.add_empty_partial(fr)
                    idx = -1
    
                part.append_point(fc,mc,pc)
                self.end[idx] = fr
        else: 
            for fc,mc,pc in zip(fsrt,msrt,psrt):
                part = self.add_empty_partial(fr)
                idx = -1
                    
                part.append_point(fc,mc,pc)
                self.end[idx] = fr
                
            
    def get_partials_at_frame(self,fr):
        '''
        Return the partials at frame fr
        '''
        partials=[]
        
        for idx, ilims in enumerate(zip(self.st,self.end)):
            if fr>=ilims[0] and fr<=ilims[1]:
                partials.append(self.partial[idx])
        
        return partials

    def get_partials_idx_at_frame(self,fr):
        '''
        Return the partials index at frame fr
        '''
        pidx=[]
        
        for idx, ilims in enumerate(zip(self.st,self.end)):
            if fr>=ilims[0] and fr<=ilims[1]:
                pidx.append(idx)
        
        return np.array(pidx)

    def get_partials_idx_ending_at_frame(self,fr):
        '''
        Return the index of the partials ending at fr
        '''
        pidx=[]
        
        for idx, ilims in enumerate(zip(self.st,self.end)):
            if fr>=ilims[0] and fr==ilims[1]:
                pidx.append(idx)
        
        return np.array(pidx)
    
    def get_points_at_frame(self,fr):
        '''
        Return the parameters of all partials at frame fr
        '''
        pass

    def plot_time_freq(self, minlen=10):
        part = [pp for pp in self.partial if len(pp.f)>minlen]
        pl.figure()
        pl.hold(True)
        for pp in part:
            pl.plot(pp.start_idx+np.arange(len(pp.f)),np.array(pp.f))
        pl.hold(False)
        pl.xlabel('Time (s)')
        pl.ylabel('Frequency (Hz)')
        pl.show()
 
    def two_plot_time_freq_mag(self, minlen=10):
        part = [pp for pp in self.partial if len(pp.f)>minlen]
        pl.figure()
        ax1=pl.subplot(211)
        pl.hold(True)
        ax2=pl.subplot(212,sharex=ax1)
        pl.hold(True)
        for pp in part:
            ax1.plot(pp.start_idx+np.arange(len(pp.f)),np.array(pp.f))
            ax2.plot(pp.start_idx+np.arange(len(pp.f)),20*np.log10(np.array(pp.mag)))
        ax1.hold(False)
        #ax1.xlabel('Time (s)')
        ax1.set_ylabel('Frequency (Hz)')
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Frequency (Hz)')
        pl.show()
    
    def plot_time_freq_mag(self, minlen=10, cm=pl.cm.rainbow):
        
        cadd=30
        cmax=256
        ccur=0
        
        part = [pp for pp in self.partial if len(pp.f)>minlen]
        pl.figure()
        pl.hold(True)
        for pp in part:
            #pl.plot(pp.start_idx+np.arange(len(pp.f)),np.array(pp.f))
            mag = 100+20*np.log10(np.array(pp.mag))
            pl.scatter(pp.start_idx+np.arange(len(pp.f)),np.array(pp.f),s=mag,c=cm(ccur),lw=0)
            ccur = np.mod(ccur+cadd,cmax)
        pl.hold(False)
        pl.xlabel('Time (s)')
        pl.ylabel('Frequency (Hz)')
        pl.show()
        
    def synth(self,sr,hop):
        w = np.zeros((max(self.end)+1)*hop)
        for part in self.partial:
            wi, spl_st = part.synth(sr,hop)
            if spl_st>=0:
                spl_end = spl_st+len(wi)
                w[spl_st:spl_end]+= wi
        return w
        
    def get_avfreq(self):
        return np.array([np.mean(xx.f) for xx in self.partial])
        
    def get_avmag(self):
        return np.array([np.mean(xx.mag) for xx in self.partial])
    
    def get_summary(self,minlen=10):
        psum=np.array([(ii,len(xx.f),np.mean(xx.f),np.mean(xx.mag)) for ii,xx in enumerate(self.partial) if len(xx.f)>minlen],dtype=[('idx','i4'),('n','i4'),('f','f4'),('mag','f4')])
        psum.sort(order='mag')    
        return psum
        
    def get_nframes(self):
        #return max([xx.start_idx+len(xx.mag)])
        return max(self.end)
        
    def get_part_data_around_freq(self, fc, semitones=.5):
        nframes = self.get_nframes()+1
        t = np.arange(nframes)/float(self.sr)*self.hop
        f = np.zeros(nframes)
        mag = np.zeros(nframes)
        ph = np.zeros(nframes)
        
        ssa = self.get_summary(minlen=0)
        ssa.sort(order='mag')
        #ssd = np.flipud(ssa)
        ss=ssa
        idx = ss['idx'][(abs(12*np.log2(abs(ss['f']/fc)))<semitones).nonzero()]
        
        for i in idx:
            sti = self.partial[i].start_idx
            endi = self.partial[i].start_idx + len(self.partial[i].mag)
            f[sti:endi] = self.partial[i].f
            mag[sti:endi] = self.partial[i].mag
            ph[sti:endi] = self.partial[i].ph
            
        return t,f,mag,ph
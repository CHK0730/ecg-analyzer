clear ; close all

% load all needed codes.
addpath('./code') ;
addpath('./code/UNSW') ;

% also load ecg-kit-0.1.6 (in code folder) if you want to run evaluation

scrsz = get(0,'ScreenSize') ;
ggg = dir('*.abf') ;


% these are indices to evaluate
AR = {};


for Jidx = 1:length(ggg)


    fprintf([ggg(Jidx).name '\n'])

    % all simulated data are saved in these mat files.
    data = abfload(ggg(Jidx).name);
    SKNAR = data(:,2) - mean(data(:,2)) ;
    Fs = 10000;  % Sampling frequency in Hz

    trend = 0 ;
    SKNAI00 = -data(:,1) - trend ;
    Wn = 1 / (Fs / 2);
    [b, a] = butter(4, Wn, 'high');
    SKNAI0 = filter(b, a, SKNAI00) ;



    x = SKNAI0;
    fprintf(['length = ' num2str(length(x)/Fs/60), 'min\n'])


    % detect R peaks
    [locsf0] = RpeakUltraLong(x(1:10:end), 1000) ;
    locsf0 = locsf0*10 ;
    % change +- of x by the sign of R peaks
    if median(x(locsf0))<0
        x= -x; SKNAI0 = -SKNAI0;
    end
    locsf = locsf0 ;

    for jj = 1: length(locsf)
        qidx = max(1, locsf(jj)-500) : min(locsf(jj)+500, length(x)) ;
        [~, b] = max(x(qidx)) ;
        locsf(jj) = max(1, locsf(jj)-500) + b(1) - 1 ;
    end
    %Remove unnormal beats
    locsf = unique(locsf) ;
    ind = ones(1,length(locsf));
    for i = 1:(length(locsf)-1)
        if locsf(i+1)-locsf(i)<100
            if x(locsf(i+1))>x(locsf(i+1))
                ind(i) = 0;
            else
                ind(i+1)=0;
            end
        end
    end

    locsf = locsf(logical(ind));
    % use the traditional BPF (other algorithms need R peaks info)
    % Normalize the passband frequencies by the Nyquist frequency
    Wn = [500 1000] / (Fs / 2) ;
    [b, a] = butter(4, Wn, 'bandpass') ;
    SKNAIbpf = filter(b, a, x) ;



    %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
    % start to apply our OS algorithm to remove ECG

    p1 = ceil((quantile(diff(locsf), .95))*1/2) ;
    p2 = ceil((quantile(diff(locsf), .95))*3/4) ;
    [~, ~, Y, YOSc, YOSc2] = OSdecomp(x, locsf, p1, p2, 0, 1) ;

    % stitch all cycles back to get cardiogenic artifact free cycles.
    [xqECG, CHECK] = stitchALL(YOSc2, locsf, length(x), p1) ;

    SKNAos0 = x - xqECG ;
    trend = smooth(medfilt1(SKNAos0, Fs/10), Fs/8, 'loess') ;

    % this is the decomposed SKNA signal
    SKNAos = SKNAos0 - trend ;

    % this is the decomposed ECG signal
    xq = xqECG + trend ;

    % collect results
    EST = [SKNAos(:) SKNAIbpf(:)];


    if 0
        % Evaluate AR (load ecg-kit-0.1.6)
        [Metrics] = EvaluatePerformance_AR1(x,EST,locsf,Fs);
        AR{Jidx} = Metrics;
    end
end

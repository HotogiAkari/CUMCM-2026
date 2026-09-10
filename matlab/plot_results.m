function plot_results
%PLOT_RESULTS 读取 result*.xlsx 与诊断 CSV，绘制论文插图（与 figures/*.png 一致）。
%
% 用法：把本文件放到项目根的 matlab/ 目录下，在 MATLAB 中直接运行
%       >> plot_results
% 输出：figures_matlab/fig1..fig6*.png
%
% 说明：本机若无 MATLAB/Octave，可先用 paper/make_figures.py 出图；
%       本脚本为等价 MATLAB 版本，数值来源完全相同（result*.xlsx / 诊断 CSV）。

root = fileparts(fileparts(mfilename('fullpath')));
resdir = fullfile(root, 'result');
diagdir = fullfile(root, 'outputs', 'diagnostics');
outdir = fullfile(root, 'figures_matlab');
if ~exist(outdir, 'dir'); mkdir(outdir); end

r = (0:0.1:2)';                      % 距中心距离 cm
t3star = 59286.175088758;            % 问题三临界时间 s
t4star = 70759.978749528;            % 问题四临界时间 s

%% 图1  问题一：温度与含水率的径向分布
T = readmatrix(fullfile(resdir, 'result1.xlsx'), 'Sheet', '温度', 'Range', 'A2');
C = readmatrix(fullfile(resdir, 'result1.xlsx'), 'Sheet', '水分浓度', 'Range', 'A2');
tk = [100 600 1200 1800];
f = figure('Position', [100 100 1000 360]);
for i = 1:2
    subplot(1, 2, i); hold on; grid on; box on
    for t = tk
        row = T(abs(T(:,1) - t) < 0.5, :);
        if i == 2, row = C(abs(C(:,1) - t) < 0.5, :); end
        plot(r, row(2:22), '-o', 'MarkerSize', 3, 'DisplayName', sprintf('t=%d s', t));
    end
    xlabel('到中心距离 r/cm');
    if i == 1, ylabel('温度 T/℃'); else, ylabel('干基含水率 C/(kg/kg)'); end
    legend('Location', 'best'); title('问题一');
end
saveas(f, fullfile(outdir, 'fig1_q1_radial.png')); close(f);

%% 图2  问题二：温度与含水率的径向分布
T2 = readmatrix(fullfile(resdir, 'result2.xlsx'), 'Sheet', '温度', 'Range', 'A2');
C2 = readmatrix(fullfile(resdir, 'result2.xlsx'), 'Sheet', '水分浓度', 'Range', 'A2');
hk = [0.5 1 1.5 2 3];
f = figure('Position', [100 100 1000 360]);
for i = 1:2
    subplot(1, 2, i); hold on; grid on; box on
    for h = hk
        row = T2(abs(T2(:,1) - h*3600) < 0.5, :);
        if i == 2, row = C2(abs(C2(:,1) - h*3600) < 0.5, :); end
        plot(r, row(2:22), '-o', 'MarkerSize', 3, 'DisplayName', sprintf('t=%g h', h));
    end
    xlabel('到中心距离 r/cm');
    if i == 1, ylabel('温度 T/℃'); else, ylabel('干基含水率 C/(kg/kg)'); end
    legend('Location', 'best'); title('问题二');
end
saveas(f, fullfile(outdir, 'fig2_q2_radial.png')); close(f);

%% 图3  问题三：含水率演化与终止判据
C3 = readmatrix(fullfile(resdir, 'result3.xlsx'), 'Sheet', 'Sheet1', 'Range', 'A2');
th = C3(:,1) / 3600;
f = figure('Position', [100 100 700 360]); hold on; grid on; box on
plot(th, C3(:,2), 'DisplayName', '中心 r=0');
plot(th, C3(:,22), 'DisplayName', '表面 r=2 cm');
yline(0.15, '--r', 'DisplayName', '判据 max C = 0.15');
xline(t3star/3600, ':k', 'HandleVisibility', 'off');
xlabel('时间 t/h'); ylabel('干基含水率 C/(kg/kg)');
title(sprintf('问题三：t* = %.4f h', t3star/3600));
legend('Location', 'best');
saveas(f, fullfile(outdir, 'fig3_q3_history.png')); close(f);

%% 图4  问题四：含水率演化与半径收缩
C4 = readmatrix(fullfile(resdir, 'result4.xlsx'), 'Sheet', 'Sheet1', 'Range', 'A2');
R = readmatrix(fullfile(root, '附件2.xlsx'), 'Sheet', 'Sheet1', 'Range', 'A2');
f = figure('Position', [100 100 700 360]);
yyaxis left; hold on; grid on
plot(C4(:,1)/3600, C4(:,2), 'DisplayName', '中心 r=0');
plot(C4(:,1)/3600, C4(:,23), 'DisplayName', '药材表面');
yline(0.15, '--r', 'DisplayName', '判据 max C = 0.15');
ylabel('干基含水率 C/(kg/kg)');
yyaxis right
plot(R(:,1)/3600, R(:,2), 'g--', 'DisplayName', '半径 R(t)');
ylabel('药材半径 R/cm');
xlabel('时间 t/h'); title(sprintf('问题四：t* = %.4f h', t4star/3600));
legend('Location', 'best');
saveas(f, fullfile(outdir, 'fig4_q4_history.png')); close(f);

%% 图5  灵敏度：临界时间随参数倍数的变化
mt = readtable(fullfile(diagdir, 'sensitivity_mass_transfer.csv'));
df = readtable(fullfile(diagdir, 'sensitivity_diffusivity.csv'));
ca = readtable(fullfile(diagdir, 'sensitivity_equilibrium_moisture.csv'));
f = figure('Position', [100 100 1100 320]);
subplot(1,3,1); plot(mt.factor,[mt.q3_t_h mt.q4_t_h],'-o'); grid on
xlabel('传质系数 h_C 倍数'); ylabel('临界时间 t*/h'); legend('问题三','问题四');
subplot(1,3,2); plot(df.factor,[df.q3_t_h df.q4_t_h],'-o'); grid on
xlabel('扩散系数 D 倍数'); ylabel('临界时间 t*/h'); legend('问题三','问题四');
subplot(1,3,3); plot(ca.factor,[ca.q3_t_h ca.q4_t_h],'-o'); grid on
xlabel('平衡含水率 C_a 倍数'); ylabel('临界时间 t*/h'); legend('问题三','问题四');
saveas(f, fullfile(outdir, 'fig5_sensitivity.png')); close(f);

%% 图6  收敛性：空间网格与时间容差
sp = readtable(fullfile(diagdir, 'space.csv'));
to = readtable(fullfile(diagdir, 'tolerance.csv'));
f = figure('Position', [100 100 1000 320]);
subplot(1,2,1); hold on; grid on
for q = ["Q3" "Q4"]
    m = sp.question == q;
    plot(sp.N(m), sp.event_time_s(m), '-o');
end
xlabel('径向区间数 N'); ylabel('临界时间 t*/s'); legend('Q3','Q4'); title('(a) 空间网格收敛');
subplot(1,2,2); hold on; grid on
plot(to.rtol, to.q3_t_h, '-o'); plot(to.rtol, to.q4_t_h, '-s');
set(gca, 'XScale', 'log');
xlabel('相对容差 rtol'); ylabel('临界时间 t*/h'); legend('问题三','问题四'); title('(b) 时间容差收敛');
saveas(f, fullfile(outdir, 'fig6_convergence.png')); close(f);

fprintf('图已输出到 %s\n', outdir);
end

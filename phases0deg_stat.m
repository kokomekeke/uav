phases_deg = phases*180/pi;
plot(phases_deg);
legend("ch0-ch1", "ch2-ch3");
xlabel("Time (bursts)");
ylabel("ROI phase difference (deg)");
ch0_ch1_rms = rms(phases_deg(:, 1))
ch0_ch1_mean = mean(phases_deg(:, 1))
ch0_ch1_std = std(phases_deg(:, 1))
ch2_ch3_rms = rms(phases_deg(:, 2))
ch2_ch3_mean = mean(phases_deg(:, 2))
ch2_ch3_std = std(phases_deg(:, 2))


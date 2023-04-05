pkg load financial
pkg load matgeom
pkg load statistics
pkg load signal
cavg = [movavg(compass(:,1),24,24) movavg(compass(:,2),24,24) movavg(compass(:,3),24,24)];
center = [(max(cavg(:,1))+min(cavg(:,1)))/2 ; (max(cavg(:,2))+min(cavg(:,2)))/2 ; (max(cavg(:,3))+min(cavg(:,3)))/2 ];

figure; title("Compass sensor values");
hold on; plot3(cavg(:,1),cavg(:,2),cavg(:,3)); plot3(center(1),center(2),center(3),'x'); grid on;

ccorr = [cavg(:,1).-center(1) cavg(:,2).-center(2) cavg(:,3).-center(3)];
angles = atan2(ccorr(:,2), ccorr(:,1));
roi_azimuth = roi(:, 1);
angles = -angles;

# roi_azimuth_filt = filter(fir1(16, 0.1), 1, roi_azimuth);

adiff = angleDiff(angles, roi_azimuth);
adiff_prev = 0;
for f=1:length(adiff)
  if isfinite(adiff(f))
    adiff(f) = adiff_prev + angleDiff(adiff_prev, adiff(f));
    adiff_prev = adiff(f);
  end
end

angles = angles .+ mean(rmmissing(adiff));
angles = angleDiff(0, angles);

adiff = angleDiff(angles, roi_azimuth);
adiff(~isfinite(adiff))=0;
##angles_prev = 0;
##for f=1:length(angles)
##  if isfinite(angles(f))
##    angles(f) = angles_prev + angleDiff(angles_prev, angles(f));
##    angles_prev = angles(f)
##  end
##end
##roi_azimuth_prev = 0;
##for f=1:length(roi_azimuth)
##  if isfinite(roi_azimuth(f))
##    roi_azimuth(f) = roi_azimuth_prev + angleDiff(roi_azimuth_prev, roi_azimuth(f));
##    roi_azimuth_prev = roi_azimuth(f)
##  end
##end
figure; title("Compass and CS measurement");
hold on;
area ( adiff ,'LineStyle','none','FaceColor','y');
plot (phases(:, 1), "LineWidth", 2, "Color", "#AAFFAA");
plot (phases(:, 2), "LineWidth", 2, "Color", "#AAAAFF");
plot (phases(:, 3), "LineWidth", 2, "Color", "#FFAAFF");
plot (angles, "m");
plot (roi_azimuth, "b");
hold off;
grid on;
legend("Error","ch0-ch1", "ch0-ch2", "ch0-ch3",  "Compass sensor", "CoreService ROI azimuth");

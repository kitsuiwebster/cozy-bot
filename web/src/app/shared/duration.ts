// Format a duration for the header stat tiles: "Xd Yh", switching to
// "Xy Yd" once it passes a year.
export function formatDaysHours(totalSeconds: number): string {
  const totalDays = Math.floor(totalSeconds / 86400);
  if (totalDays >= 365) {
    const years = Math.floor(totalDays / 365);
    const days = totalDays % 365;
    return `${years}y ${days}d`;
  }
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  return `${totalDays}d ${hours}h`;
}

import { HttpInterceptorFn } from '@angular/common/http';
import { timeout } from 'rxjs/operators';

// 15s ceiling on every HTTP request. Without this, the public API stalling
// (network blip, dead VPS) leaves the UI spinning forever instead of surfacing
// the failure.
export const HTTP_TIMEOUT_MS = 15000;

export const timeoutInterceptor: HttpInterceptorFn = (req, next) => {
  return next(req).pipe(timeout(HTTP_TIMEOUT_MS));
};

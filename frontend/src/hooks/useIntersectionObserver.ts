import { useEffect, type RefObject } from "react";

export function useIntersectionObserver(
  ref: RefObject<Element | null>,
  onIntersect: () => void,
) {
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => entries[0]?.isIntersecting && onIntersect(),
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref, onIntersect]);
}

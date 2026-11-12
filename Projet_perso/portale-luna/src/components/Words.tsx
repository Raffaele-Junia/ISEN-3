import { Fragment } from "react";

/** A line split into word spans (each `data-word`, for the word-by-word reveal), with the spaces kept as text. */
export function Words({ text, className }: { text: string; className?: string }) {
  const words = text.split(" ");
  return (
    <>
      {words.map((word, i) => (
        <Fragment key={i}>
          <span className={className} data-word="">
            {word}
          </span>
          {i < words.length - 1 ? " " : null}
        </Fragment>
      ))}
    </>
  );
}

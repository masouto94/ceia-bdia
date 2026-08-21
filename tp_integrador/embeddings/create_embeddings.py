from sentence_transformers import SentenceTransformer
import re


def chunk_sentences(text, size=500, overlap=50):
    """Divide respetando límites de oraciones."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= size:
            current_chunk += " " + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # arrancar el siguiente chunk con solapamiento
            word_overlap = current_chunk[-overlap:] if overlap else ""
            current_chunk = word_overlap + " " + sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def vectorize_chunks(model, chunks):
    """Convierte una lista de chunks en sus embeddings correspondientes."""
    embeddings = model.encode(chunks, normalize_embeddings=True)
    return embeddings.tolist()


if __name__ == "__main__":
    # Ejemplo de uso
    model = SentenceTransformer("all-MiniLM-L6-v2")  # 384 dimensiones
    text = """ Lorem ipsum dolor sit amet, consectetur adipiscing elit. Phasellus tincidunt aliquam magna, ut consectetur ipsum tempus at. In lacus magna, pretium eget nulla non, condimentum ultricies nibh. Nullam eu ex tortor. Quisque rutrum maximus quam, quis fringilla ex accumsan semper. Vestibulum euismod fermentum justo, et suscipit velit venenatis ut. Aliquam sit amet venenatis nibh. Sed dictum, velit vel condimentum placerat, velit nunc convallis eros, quis venenatis ante odio a augue. Ut nec eleifend est, ac tincidunt odio. Donec rhoncus, augue ac vestibulum ultricies, ipsum neque ullamcorper justo, vel hendrerit diam risus et ex. Nullam rhoncus, lectus quis vestibulum sollicitudin, lectus eros imperdiet libero, a posuere diam augue non nisi. Fusce laoreet tincidunt consectetur.

Ut fringilla maximus arcu, et auctor nisi gravida ut. Curabitur blandit ornare tortor a finibus. Duis mollis pharetra massa, vitae luctus nisi ultrices vel. Duis a sagittis sapien, nec venenatis lacus. Fusce vel egestas tortor, eu placerat est. Fusce interdum, risus nec laoreet finibus, ipsum ligula hendrerit sem, at cursus justo est vel nisi. Suspendisse cursus mauris at imperdiet dapibus. Morbi dapibus, enim ut consequat rhoncus, est mi maximus dui, eu ornare purus metus in ligula. Cras tincidunt diam ac pulvinar congue. Sed porttitor tempor est, id sollicitudin nisl mollis ac. Nullam vel lorem dictum, elementum massa sed, volutpat dolor. Maecenas lacinia justo vitae odio aliquam commodo at eu nibh. Maecenas quam odio, mollis vitae lacinia vitae, dignissim a massa. Pellentesque aliquet laoreet egestas. Nullam dapibus scelerisque urna vitae laoreet. Etiam malesuada purus at accumsan condimentum.

Vestibulum faucibus feugiat laoreet. Pellentesque commodo ullamcorper justo quis sagittis. Sed sed lacinia tortor, non dignissim massa. Donec non mi sit amet mi tristique accumsan vel a ligula. Sed vitae leo dolor. Fusce a dui turpis. Phasellus sapien lacus, pellentesque nec feugiat ut, pretium ac turpis. In efficitur nisi sodales laoreet feugiat. Etiam nulla lectus, tincidunt a felis tincidunt, elementum tristique quam. Donec eu malesuada purus. Pellentesque laoreet mattis fringilla.

Vivamus dignissim ante quis mi luctus elementum. In sollicitudin sagittis sapien, eu fermentum elit lobortis in. Etiam facilisis erat vel porta sagittis. Integer molestie vestibulum ullamcorper. Suspendisse eget pretium arcu. Mauris tincidunt, nibh non congue sollicitudin, metus ante ornare arcu, sit amet consequat dui risus in nulla. In hac habitasse platea dictumst. Aliquam egestas arcu orci, sit amet hendrerit odio blandit in. Etiam fermentum nibh ante, sit amet blandit velit consequat quis. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Etiam tellus tortor, congue sit amet dignissim quis, dictum vehicula ligula. Praesent lacinia nisi mattis, consequat mauris laoreet, porta sapien. Vestibulum at eleifend est. Mauris et ipsum lectus. In fermentum nisl consequat orci dictum efficitur.

Vestibulum vestibulum nec libero non semper. Pellentesque arcu nibh, tristique euismod tellus id, vehicula efficitur risus. Fusce eleifend ipsum pellentesque lobortis fringilla. Quisque elementum id felis id ullamcorper. Quisque vitae orci odio. Phasellus ut aliquam sapien. Sed feugiat mauris sed blandit mattis. Nam eu odio tincidunt, fermentum eros eget, cursus est. Maecenas erat enim, porttitor et ultrices vel, eleifend vitae libero. Donec ac lectus rhoncus velit sagittis egestas eu in sem. Mauris aliquam at arcu sed feugiat. Sed at facilisis urna. """
    chunks = chunk_sentences(text)
    embeddings = vectorize_chunks(model, chunks)

    # chunks y embeddings quedan en memoria, listos para insertarse
    # a Postgres (pgvector) con psycopg desde otro script.
    for i, (chunk, vector) in enumerate(zip(chunks, embeddings)):
        print(f"[{i}] {len(vector)} dims - {chunk[:60]!r}...")

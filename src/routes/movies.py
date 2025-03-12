from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, MovieModel
from schemas.movies import MovieDetailResponseSchema, MovieListResponseSchema

router = APIRouter()


@router.get("/movies/{movie_id}/", response_model=MovieDetailResponseSchema)
async def get_movie_by_id(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie with the given ID was not found.")
    return movie


def get_pagination_params(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=20)
):
    return {"page": page, "per_page": per_page}


@router.get("/movies/", response_model=MovieListResponseSchema)
async def get_list_movies(
        pagination: dict = Depends(get_pagination_params),
        db: AsyncSession = Depends(get_db)
):
    page = pagination["page"]
    per_page = pagination["per_page"]

    result = await db.execute(
        select(MovieModel)
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    movies = result.scalars().all()

    if not movies:
        raise HTTPException(status_code=404, detail="No movies found.")

    total_items = await db.scalar(select(func.count()).select_from(MovieModel))
    total_pages = (total_items + per_page - 1) // per_page

    rut_url = "/api/v1/theater/"
    response = {
        "movies": [MovieDetailResponseSchema.from_orm(movie) for movie in movies],
        "prev_page": f"{rut_url}movies/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        "next_page": f"{rut_url}movies/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        "total_pages": total_pages,
        "total_items": total_items
    }

    return response

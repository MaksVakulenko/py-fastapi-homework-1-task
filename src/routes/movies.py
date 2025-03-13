from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from database import get_db, MovieModel
from schemas.movies import (
    MovieDetailResponseSchema,
    MovieListResponseSchema,
    MovieCreateRequestSchema,
    MovieUpdateRequestSchema
)

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


@router.post("/movies/", response_model=MovieDetailResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_movie(movie: MovieCreateRequestSchema, db: AsyncSession = Depends(get_db)):
    if len(movie.name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name must not exceed 255 characters."
        )

    one_year_from_now = date.today() + timedelta(days=365)
    if movie.date > one_year_from_now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Movie date must not be more than one year in the future."
        )

    if not (0 <= movie.score <= 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Score must be between 0 and 100."
        )

    if movie.budget < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget must be a non-negative number."
        )
    if movie.revenue < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Revenue must be a non-negative number."
        )

    duplicate_query = await db.execute(
        select(MovieModel).where(
            MovieModel.name == movie.name,
            MovieModel.date == movie.date
        )
    )
    existing_movie = duplicate_query.scalar_one_or_none()
    if existing_movie:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A movie with the name '{movie.name}' and release date '{movie.date}' already exists."
        )

    new_movie = MovieModel(
        name=movie.name,
        date=movie.date,
        score=movie.score,
        genre=movie.genre,
        overview=movie.overview,
        crew=movie.crew,
        orig_title=movie.orig_title,
        status=movie.status,
        orig_lang=movie.orig_lang,
        budget=movie.budget,
        revenue=movie.revenue,
        country=movie.country
    )

    db.add(new_movie)
    await db.commit()
    await db.refresh(new_movie)

    return new_movie


@router.delete("/movies/{movie_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(movie_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    movie = result.scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    await db.delete(movie)
    await db.commit()


@router.patch("/movies/{movie_id}/", status_code=status.HTTP_200_OK)
async def update_movie(movie_id: int, data: MovieUpdateRequestSchema, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MovieModel).where(MovieModel.id == movie_id))
    existing_movie = result.scalar_one_or_none()
    if not existing_movie:
        raise HTTPException(
            status_code=404,
            detail="Movie with the given ID was not found."
        )

    if data.score is not None:
        if not (0 <= data.score <= 100):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input data."
            )
        existing_movie.score = data.score

    if data.budget is not None:
        if data.budget < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input data."
            )
        existing_movie.budget = data.budget

    if data.revenue is not None:
        if data.revenue < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid input data."
            )
        existing_movie.revenue = data.revenue

    if data.name is not None:
        existing_movie.name = data.name

    if data.date is not None:
        existing_movie.date = data.date

    if data.overview is not None:
        existing_movie.overview = data.overview

    if data.status is not None:
        existing_movie.status = data.status

    await db.commit()

    return {"detail": "Movie updated successfully."}
